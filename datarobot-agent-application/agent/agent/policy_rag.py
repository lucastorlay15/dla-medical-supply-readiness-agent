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

"""Tool 2 client for the deployed DataRobot medical-policy RAG blueprint."""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

POLICY_RAG_DEPLOYMENT_ID = os.environ.get(
    "POLICY_RAG_DEPLOYMENT_ID", "6a7cacedc2b2963a534e041b"
)


def _find_citations(value: Any) -> list[Any]:
    """Find citation collections anywhere in the Bolt-on Governance response."""
    found: list[Any] = []
    if isinstance(value, dict):
        citations = value.get("citations")
        if isinstance(citations, list):
            found.extend(citations)
        for child in value.values():
            found.extend(_find_citations(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_citations(child))
    return found


def _citation_label(citation: Any) -> str | None:
    if isinstance(citation, str):
        return citation.strip() or None
    if not isinstance(citation, dict):
        return None

    for key in ("source", "document_file_path", "title", "url"):
        value = citation.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = citation.get("metadata")
    if isinstance(metadata, dict):
        for key in ("source", "document_file_path", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def query_policy_rag(question: str) -> str:
    """Retrieve grounded synthetic medical-policy guidance from DataRobot RAG."""
    endpoint = os.environ.get(
        "DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2"
    ).rstrip("/")
    api_token = os.environ.get("DATAROBOT_API_TOKEN", "")

    if not api_token:
        return "Policy RAG retrieval failed: DATAROBOT_API_TOKEN is not available."

    url = (
        f"{endpoint}/deployments/{POLICY_RAG_DEPLOYMENT_ID}/chat/completions"
    )
    payload = {
        "model": "datarobot-deployed-llm",
        "messages": [{"role": "user", "content": question}],
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return f"Policy RAG retrieval failed with HTTP {exc.code}: {detail[:500]}"
    except (URLError, TimeoutError) as exc:
        return f"Policy RAG retrieval failed: {exc}"
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        return f"Policy RAG retrieval failed while parsing the response: {exc}"

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "Policy RAG retrieval failed: no assistant content was returned."

    labels: list[str] = []
    for citation in _find_citations(result):
        label = _citation_label(citation)
        if label and label not in labels:
            labels.append(label)

    if labels:
        sources = "\n".join(f"- {label}" for label in labels[:8])
        return f"{content}\n\nRetrieved policy sources:\n{sources}"
    return str(content)
