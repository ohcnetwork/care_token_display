import logging
import re
from urllib.parse import urlencode

from care.emr.models import Token, TokenSubQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)
from care.security.authorization import AuthorizationController
from django.db.models import Exists, OuterRef
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_naive
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from token_display.authentication import QueryParamTokenAuthentication
from token_display.settings import plugin_settings
from token_display.tts import TTSError, render_announcement
from token_display.utils import (
    fmt_schedule_resource_name,
    fmt_token_number,
)

logger = logging.getLogger(__name__)

TRUTHY_QUERY_VALUES = {"1", "true", "yes"}

# BCP-47 language tag: letters, digits and hyphens, up to 35 chars
# (see RFC 5646 — 35 chars covers any realistic tag).
_LANG_RE = re.compile(r"^[A-Za-z0-9-]{1,35}$")
_DEFAULT_LANG = "en-US"

# Voice id whitelist character set; the value must additionally exist in the
# configured TTS_VOICE_CATALOG before it is accepted.
_VOICE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

# Token codes are produced by ``utils.fmt_token_number`` as
# ``f"{shorthand}-{number:03d}"``. We keep the validator strict so that the
# string is safe to feed into a TTS prompt without any escaping concerns.
_TOKEN_CODE_RE = re.compile(r"^[A-Za-z]{1,4}-\d{1,4}$")

_DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def _parse_bool_query_param(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in TRUTHY_QUERY_VALUES


def _parse_lang_query_param(value: str | None) -> str:
    if value and _LANG_RE.match(value):
        return value
    return _DEFAULT_LANG


def _resolve_voice(value: str | None) -> str:
    """Pick a voice id, falling back to the default if ``value`` is empty.

    Returns ``None`` if ``value`` is non-empty but not whitelisted so the
    caller can return a 400.
    """
    catalog = plugin_settings.TTS_VOICE_CATALOG or {}
    default = plugin_settings.TTS_DEFAULT_VOICE
    if not value:
        return default if default in catalog else ""
    if not _VOICE_RE.match(value) or value not in catalog:
        return ""
    return value


def _format_spoken_code(code: str) -> str:
    """Convert ``"G-001"`` into ``"G, zero zero one"`` for cleaner TTS."""
    parts = []
    for segment in code.split("-"):
        if segment.isdigit():
            parts.append(" ".join(_DIGIT_WORDS[d] for d in segment))
        else:
            parts.append(segment)
    return ", ".join(parts)


def _build_announcement_url(
    sub_queue_external_id: str,
    token_code: str,
    *,
    token: str,
    lang: str,
    voice: str,
) -> str:
    path = reverse(
        "token-announcement",
        kwargs={
            "sub_queue_external_id": sub_queue_external_id,
            "token_code": token_code,
        },
    )
    query = {"lang": lang}
    if voice:
        query["voice"] = voice
    if token:
        query["token"] = token
    return f"{path}?{urlencode(query)}"


class SubQueuesTokenDisplayView(APIView):
    """
    Main view that renders the full SSR token display page for a facility.
    """

    authentication_classes = [QueryParamTokenAuthentication]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "token_display/display.html"

    def get_sub_queue_objects(self, only_with_active_tokens: bool = False):
        external_ids = self.kwargs["sub_queue_external_ids"].split(",")
        sub_queues = TokenSubQueue.objects.filter(
            external_id__in=external_ids,
            status=TokenSubQueueStatusOptions.active.value,
        )
        if only_with_active_tokens:
            active_token_exists = Token.objects.filter(
                sub_queue=OuterRef("pk"),
                queue__resource=OuterRef("resource"),
                queue__date=make_naive(timezone.now()).date(),
                queue__is_primary=True,
                status__in=[
                    TokenStatusOptions.CREATED.value,
                    TokenStatusOptions.IN_PROGRESS.value,
                ],
            )
            sub_queues = sub_queues.annotate(
                _has_active_tokens=Exists(active_token_exists)
            ).filter(_has_active_tokens=True)
        order = {external_id: index for index, external_id in enumerate(external_ids)}
        return sorted(sub_queues, key=lambda sq: order.get(str(sq.external_id), len(order)))

    def authorize_request(self):
        # Authorize against the unfiltered set so permission errors are not
        # masked by the active-tokens filter.
        for sub_queue in self.get_sub_queue_objects():
            if not AuthorizationController.call(
                "can_list_token", sub_queue.resource, self.request.user
            ):
                raise PermissionDenied(
                    "You do not have permission read tokens for this resource"
                )

    def get(self, request, sub_queue_external_ids: str):
        """
        Render the full token display page with static data.
        """
        self.authorize_request()
        only_with_active_tokens = _parse_bool_query_param(
            request.query_params.get("only_with_active_tokens")
        )
        lang = _parse_lang_query_param(request.query_params.get("lang"))
        mute = _parse_bool_query_param(request.query_params.get("mute"))
        voice = _resolve_voice(request.query_params.get("voice"))
        access_token = request.query_params.get("token", "")
        sub_queues = self.get_sub_queue_objects(
            only_with_active_tokens=only_with_active_tokens
        )
        item_count = len(sub_queues)

        # Determine grid class and column spans
        if item_count == 1:
            grid_class = "grid-cols-1"
        elif item_count < 5:
            grid_class = "grid-cols-2"
        else:
            grid_class = "grid-cols-6"

        # Calculate column spans and fetch token data for each sub-queue
        sub_queues_with_data = []
        for index, sub_queue in enumerate(sub_queues):
            if item_count == 3 and index == 2:
                col_span = "col-span-2"
            elif item_count <= 4:
                col_span = "col-span-1"
            else:
                # For 6-column grid
                last_row_count = item_count % 3
                if last_row_count == 1 and index == item_count - 1:
                    col_span = "col-span-6"
                elif last_row_count == 2 and index >= item_count - 2:
                    col_span = "col-span-3"
                else:
                    col_span = "col-span-2"

            # Fetch the current token for this sub-queue
            token = (
                Token.objects.filter(
                    queue__resource=sub_queue.resource,
                    queue__date=make_naive(timezone.now()).date(),
                    queue__is_primary=True,
                    sub_queue=sub_queue,
                    status=TokenStatusOptions.IN_PROGRESS.value,
                )
                .order_by("created_date")
                .first()
            )

            token_code = fmt_token_number(token) if token else None
            resource_name = fmt_schedule_resource_name(sub_queue.resource)
            announcement_url = None
            if token_code and plugin_settings.TTS_ENABLED and not mute:
                announcement_url = _build_announcement_url(
                    str(sub_queue.external_id),
                    token_code,
                    token=access_token,
                    lang=lang,
                    voice=voice,
                )
            sub_queues_with_data.append(
                {
                    "id": str(sub_queue.external_id),
                    "col_span": col_span,
                    "sub_queue_name": sub_queue.name,
                    "resource_name": resource_name,
                    "token": token_code or "--",
                    "token_code": token_code,
                    "announcement_url": announcement_url,
                }
            )

        announcement_payload = {
            "sub_queues": [
                {
                    "id": entry["id"],
                    "token_code": entry["token_code"],
                    "sub_queue_name": entry["sub_queue_name"],
                    "resource_name": entry["resource_name"],
                    "announcement_url": entry["announcement_url"],
                }
                for entry in sub_queues_with_data
            ],
            "lang": lang,
            "voice": voice,
            "mute": mute,
            "auto_refresh_interval": plugin_settings.AUTO_REFRESH_INTERVAL,
        }

        return Response(
            {
                "sub_queues": sub_queues_with_data,
                "item_count": item_count,
                "auto_refresh_interval": plugin_settings.AUTO_REFRESH_INTERVAL,
                "grid_class": grid_class,
                "only_with_active_tokens": only_with_active_tokens,
                "announcement_payload": announcement_payload,
            }
        )


class TokenAnnouncementView(APIView):
    """
    Stream a single WAV containing the chime + a spoken announcement for one
    token belonging to one sub-queue. The audio is generated server-side via
    Piper TTS and cached on disk so subsequent requests for the same
    ``(voice, text)`` are near-instant.
    """

    authentication_classes = [QueryParamTokenAuthentication]

    def get(self, request, sub_queue_external_id: str, token_code: str):
        if not plugin_settings.TTS_ENABLED:
            return Response(
                {"detail": "TTS is disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not _TOKEN_CODE_RE.match(token_code):
            raise Http404("invalid token code")

        sub_queue = get_object_or_404(
            TokenSubQueue,
            external_id=sub_queue_external_id,
            status=TokenSubQueueStatusOptions.active.value,
        )

        if not AuthorizationController.call(
            "can_list_token", sub_queue.resource, request.user
        ):
            raise PermissionDenied(
                "You do not have permission to read tokens for this resource"
            )

        voice = _resolve_voice(request.query_params.get("voice"))
        if not voice:
            return Response(
                {"detail": "voice is not configured or not in catalog."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resource_name = fmt_schedule_resource_name(sub_queue.resource) or ""
        text = (
            f"Token {_format_spoken_code(token_code)}, "
            f"please proceed to {resource_name}"
        )

        try:
            wav_path = render_announcement(voice, text)
        except TTSError as exc:
            logger.warning(
                "TTS render failed for sub_queue=%s code=%s voice=%s: %s",
                sub_queue_external_id,
                token_code,
                voice,
                exc,
            )
            return Response(
                {"detail": "speech synthesis is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response = FileResponse(
            wav_path.open("rb"),
            content_type="audio/wav",
        )
        response["Content-Length"] = str(wav_path.stat().st_size)
        # The (voice, text) tuple is content-addressed by sha256 in the URL's
        # token_code + query string, so the bytes for a given URL never change.
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
