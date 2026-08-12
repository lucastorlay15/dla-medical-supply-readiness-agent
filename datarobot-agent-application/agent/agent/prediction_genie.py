# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tool 3: thin Databricks Genie Conversation API adapter.

This deliberately avoids provisioning a second MCP client or adding new DataRobot
runtime-parameter definitions. It reuses the already-proven Tool 1 Databricks
Authorization header from EXTERNAL_MCP_HEADERS and calls the dedicated Medical
Supply Forecast Genie through its standard Conversation API.
"""

import asyncio
import json
import os
from typing import Any
from urllib import error, request

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

DATABRICKS_HOST = "https://adb-7405616979247625.5.azuredatabricks.net"
FORECAST_GENIE_SPACE_ID = "01f1967fa4241a3b8f46886b69ca2875"
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}


class PredictionGenieConfig(FunctionBaseConfig, name="prediction_genie"):
    """Configuration marker for the prediction-only Genie tool."""


def _authorization_header() -> str:
    """Reuse the Databricks Authorization header already configured for Tool 1."""
    raw_headers = os.environ.get("EXTERNAL_MCP_HEADERS", "").strip()
    if not raw_headers:
        raise RuntimeError(
            "Tool 3 requires the existing EXTERNAL_MCP_HEADERS configuration used "
            "by Tool 1."
        )

    try:
        headers = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise RuntimeError("EXTERNAL_MCP_HEADERS is not valid JSON.") from exc

    authorization = headers.get("Authorization")
    if not isinstance(authorization, str) or not authorization.strip():
        raise RuntimeError(
            "EXTERNAL_MCP_HEADERS does not contain a usable Authorization header."
        )
    return authorization.strip()


def _request_json(
    method: str,
    path: str,
    authorization: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a small authenticated Databricks REST request using only stdlib."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        f"{DATABRICKS_HOST}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Databricks Genie API returned HTTP {exc.code}: {detail[:1000]}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Databricks Genie API: {exc}") from exc


def _extract_text(attachment: dict[str, Any]) -> str | None:
    text = attachment.get("text")
    if not isinstance(text, dict):
        return None
    value = text.get("content") or text.get("text")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _format_query_result(result_payload: dict[str, Any]) -> list[dict[str, Any]]:
    statement = result_payload.get("statement_response")
    if not isinstance(statement, dict):
        return []

    manifest = statement.get("manifest") or {}
    schema = manifest.get("schema") or {}
    columns = schema.get("columns") or []
    names = [
        column.get("name", f"column_{idx}") if isinstance(column, dict) else f"column_{idx}"
        for idx, column in enumerate(columns)
    ]

    result = statement.get("result") or {}
    rows = result.get("data_array") or []
    formatted: list[dict[str, Any]] = []
    for row in rows[:50]:
        if isinstance(row, list):
            formatted.append(
                {name: row[idx] if idx < len(row) else None for idx, name in enumerate(names)}
            )
    return formatted


def _run_prediction_query(question: str) -> str:
    authorization = _authorization_header()
    start = _request_json(
        "POST",
        f"/api/2.0/genie/spaces/{FORECAST_GENIE_SPACE_ID}/start-conversation",
        authorization,
        {"content": question},
    )

    conversation = start.get("conversation") or {}
    message = start.get("message") or {}
    conversation_id = conversation.get("id") or message.get("conversation_id")
    message_id = message.get("message_id") or message.get("id")
    if not conversation_id or not message_id:
        raise RuntimeError("Genie did not return conversation/message identifiers.")

    message_path = (
        f"/api/2.0/genie/spaces/{FORECAST_GENIE_SPACE_ID}/conversations/"
        f"{conversation_id}/messages/{message_id}"
    )

    response: dict[str, Any] = message
    for attempt in range(45):
        status = str(response.get("status", "")).upper()
        if status in TERMINAL_STATUSES:
            break
        asyncio.run(asyncio.sleep(min(1.0 + attempt * 0.15, 4.0)))
        response = _request_json("GET", message_path, authorization)
    else:
        raise RuntimeError("Forecast Genie timed out before reaching a terminal status.")

    status = str(response.get("status", "")).upper()
    if status != "COMPLETED":
        raise RuntimeError(
            f"Forecast Genie finished with status {status}: {response.get('error')}"
        )

    attachments = response.get("attachments") or []
    text_parts: list[str] = []
    query_results: list[dict[str, Any]] = []

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        text_value = _extract_text(attachment)
        if text_value:
            text_parts.append(text_value)

        if isinstance(attachment.get("query"), dict):
            attachment_id = attachment.get("attachment_id")
            if attachment_id:
                result_path = (
                    f"{message_path}/attachments/{attachment_id}/query-result"
                )
                result_payload = _request_json("GET", result_path, authorization)
                query_results.extend(_format_query_result(result_payload))

    output: dict[str, Any] = {
        "source": "Medical Supply Forecast Genie over DataRobot-generated predictions",
        "question": question,
    }
    if text_parts:
        output["genie_summary"] = "\n".join(text_parts)
    if query_results:
        output["rows"] = query_results

    if len(output) == 2:
        output["attachments"] = attachments

    return json.dumps(output, ensure_ascii=False)


@register_function(config_type=PredictionGenieConfig)
async def prediction_genie(_config: PredictionGenieConfig, _builder: Builder):
    """Register the prediction-only Genie as a first-class NAT function."""

    async def _query(question: str) -> str:
        """Analyze DataRobot-generated 30-day shortage predictions with Forecast Genie."""
        return await asyncio.to_thread(_run_prediction_query, question)

    yield FunctionInfo.from_fn(
        _query,
        description=(
            "Tool 3: analyze authoritative DataRobot-generated 30-day shortage "
            "probabilities using the dedicated Medical Supply Forecast Genie. Use for "
            "prediction rankings, filters, thresholds, and grouped risk summaries; do "
            "not use for operational root cause or policy."
        ),
    )
