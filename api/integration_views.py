from __future__ import annotations

from django.http import HttpResponse
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers

from .integration_auth import DeveloperApiKeyAuthentication
from .integration_serializers import (
    DataAccessDecisionSerializer,
    DataAccessRequestSerializer,
    DeveloperApiKeySerializer,
    DeveloperAppSerializer,
    ExternalAccessRequestCreateSerializer,
    serialize_medicine_history_queryset,
    set_request_status,
)
from .models import DataAccessRequest, DeveloperApiKey, DeveloperApp, MedicineHistoryEntry
from .pagination import StandardPagination
from .xml_utils import build_medicine_history_xml, build_paginated_medicine_history_xml, xml_content_type


@extend_schema_view(
    list=extend_schema(summary="List developer apps", description="List developer apps owned by the authenticated user."),
    create=extend_schema(summary="Create developer app"),
    retrieve=extend_schema(summary="Get developer app", parameters=[OpenApiParameter("id", int, OpenApiParameter.PATH)]),
    partial_update=extend_schema(summary="Update developer app", parameters=[OpenApiParameter("id", int, OpenApiParameter.PATH)]),
    destroy=extend_schema(summary="Delete developer app", parameters=[OpenApiParameter("id", int, OpenApiParameter.PATH)]),
)
class DeveloperAppViewSet(viewsets.ModelViewSet):
    serializer_class = DeveloperAppSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeveloperApp.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List developer API keys"),
    create=extend_schema(
        summary="Create developer API key",
        description="Creates a key for an owned app. Raw `api_key` is returned once and cannot be retrieved later.",
        responses={
            201: inline_serializer(
                name="DeveloperApiKeyCreateResponse",
                fields={
                    "id": serializers.IntegerField(),
                    "app": serializers.IntegerField(),
                    "name": serializers.CharField(),
                    "key_prefix": serializers.CharField(),
                    "last_used_at": serializers.DateTimeField(allow_null=True),
                    "revoked_at": serializers.DateTimeField(allow_null=True),
                    "created_at": serializers.DateTimeField(),
                    "api_key": serializers.CharField(),
                },
            )
        },
        examples=[
            OpenApiExample(
                "CreateKeyResponse",
                value={
                    "id": 7,
                    "app": 2,
                    "name": "primary",
                    "key_prefix": "dev_abcd1234",
                    "last_used_at": None,
                    "revoked_at": None,
                    "created_at": "2026-05-03T19:00:00Z",
                    "api_key": "dev_abcd1234_raw_key_value",
                },
                response_only=True,
            )
        ],
    ),
)
class DeveloperApiKeyViewSet(viewsets.GenericViewSet, generics.CreateAPIView, generics.ListAPIView):
    serializer_class = DeveloperApiKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeveloperApiKey.objects.select_related("app").filter(app__owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        payload = dict(serializer.data)
        payload["api_key"] = getattr(serializer.instance, "raw_key", None)
        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)


class RevokeDeveloperApiKeyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Revoke developer API key",
        request=None,
        responses={200: OpenApiResponse(description="API key revoked"), 404: OpenApiResponse(description="Not found")},
    )
    def post(self, request, key_id: int):
        try:
            key = DeveloperApiKey.objects.select_related("app").get(id=key_id, app__owner=request.user)
        except DeveloperApiKey.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        key.revoke()
        return Response({"detail": "API key revoked."})


class ExternalCreateAccessRequestView(APIView):
    authentication_classes = [DeveloperApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create external access request",
        description="Creates an access request for a target username using API-key auth.",
        request=ExternalAccessRequestCreateSerializer,
        responses={
            201: DataAccessRequestSerializer,
            400: OpenApiResponse(description="Invalid payload or unknown username"),
            401: OpenApiResponse(description="Missing, invalid, or revoked API key"),
            409: OpenApiResponse(description="Active request already exists for app/user"),
        },
        examples=[
            OpenApiExample(
                "CreateAccessRequest",
                value={"username": "patient1", "purpose": "Care coordination"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = ExternalAccessRequestCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        api_key: DeveloperApiKey = request.auth
        target_user = serializer.context["target_user"]
        purpose = serializer.validated_data.get("purpose", "")

        if DataAccessRequest.objects.filter(
            app=api_key.app,
            target_user=target_user,
            status__in=[DataAccessRequest.STATUS_PENDING, DataAccessRequest.STATUS_APPROVED],
        ).exists():
            return Response(
                {"detail": "An active request already exists for this user and app."},
                status=status.HTTP_409_CONFLICT,
            )
        request_obj = DataAccessRequest.objects.create(
            app=api_key.app,
            target_user=target_user,
            purpose=purpose,
        )

        return Response(DataAccessRequestSerializer(request_obj).data, status=status.HTTP_201_CREATED)


class UserAccessRequestInboxView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List incoming access requests", request=None, responses={200: DataAccessRequestSerializer(many=True)})
    def get(self, request):
        queryset = DataAccessRequest.objects.select_related("app", "app__owner", "target_user").filter(
            target_user=request.user
        )
        return Response(DataAccessRequestSerializer(queryset, many=True).data)


class AccessRequestDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def _resolve_request(self, request_id: int, user):
        try:
            return DataAccessRequest.objects.select_related("target_user").get(id=request_id, target_user=user)
        except DataAccessRequest.DoesNotExist:
            return None

    @extend_schema(
        summary="Approve/reject/revoke access request",
        description="Decision is selected by URL segment: approve, reject, or revoke.",
        request=DataAccessDecisionSerializer,
        responses={
            200: DataAccessRequestSerializer,
            400: OpenApiResponse(description="Invalid decision"),
            404: OpenApiResponse(description="Request not found for current user"),
        },
    )
    def post(self, request, request_id: int, decision: str):
        access_request = self._resolve_request(request_id, request.user)
        if not access_request:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DataAccessDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data.get("decision_note", "")

        if decision == "approve":
            status_value = DataAccessRequest.STATUS_APPROVED
        elif decision == "reject":
            status_value = DataAccessRequest.STATUS_REJECTED
        elif decision == "revoke":
            status_value = DataAccessRequest.STATUS_REVOKED
        else:
            return Response({"detail": "Invalid decision."}, status=status.HTTP_400_BAD_REQUEST)

        set_request_status(access_request, status_value, note)
        return Response(DataAccessRequestSerializer(access_request).data)


class ExternalMedicineHistoryView(APIView):
    authentication_classes = [DeveloperApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Fetch approved user's medicine history",
        description="Returns paginated medicine history for a user only when this app has approved consent.",
        parameters=[
            OpenApiParameter(name="username", location=OpenApiParameter.PATH, required=True, type=str),
            OpenApiParameter(name="format", location=OpenApiParameter.QUERY, required=False, type=str, description="json (default) or xml"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, required=False, type=int),
            OpenApiParameter(name="page_size", location=OpenApiParameter.QUERY, required=False, type=int),
        ],
        request=None,
        responses={
            200: OpenApiResponse(description="JSON paginated payload or XML document"),
            401: OpenApiResponse(description="Invalid API key"),
            403: OpenApiResponse(description="No approved access request"),
        },
    )
    def get(self, request, username: str):
        api_key: DeveloperApiKey = request.auth
        if not DataAccessRequest.objects.filter(
            app=api_key.app,
            target_user__username=username,
            status=DataAccessRequest.STATUS_APPROVED,
        ).exists():
            return Response(
                {"detail": "No approved access request for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = MedicineHistoryEntry.objects.filter(user__username=username).select_related("medicine")

        paginator = StandardPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serialized_rows = serialize_medicine_history_queryset(paginated)
        payload = paginator.get_paginated_response(serialized_rows).data

        output_format = request.query_params.get("format", "json").lower()
        if output_format == "xml":
            xml_bytes = build_paginated_medicine_history_xml(payload)
            return HttpResponse(xml_bytes, content_type=xml_content_type())

        return Response(payload)


class MedicineHistoryExportXmlView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export own medicine history as XML",
        request=None,
        responses={200: OpenApiResponse(description="XML attachment")},
    )
    def get(self, request):
        queryset = MedicineHistoryEntry.objects.filter(user=request.user).select_related("medicine")
        data = serialize_medicine_history_queryset(queryset)
        xml_bytes = build_medicine_history_xml(data)
        response = HttpResponse(xml_bytes, content_type=xml_content_type())
        response["Content-Disposition"] = 'attachment; filename="medicine_history.xml"'
        return response
