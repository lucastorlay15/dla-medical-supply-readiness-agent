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
from typing import Annotated

from datarobot_genai.core.telemetry.agent import instrument
from datarobot_genai.dragent.tool import nat_tool

from agent.policy_rag import query_policy_rag

instrument()


def policy_rag(
    question: Annotated[
        str,
        "A policy, stocking-rule, readiness-rule, sourcing, supplier-escalation, "
        "or cold-chain guidance question to answer from the synthetic medical "
        "policy knowledge base.",
    ],
) -> str:
    """Retrieve grounded medical-policy guidance from the DataRobot RAG deployment."""
    return query_policy_rag(question)


nat_tool(
    policy_rag,
    "policy_rag",
    description=(
        "Tool 2: retrieve authoritative guidance from the synthetic DLA Medical "
        "Policy RAG knowledge base. Use for stocking requirements, readiness "
        "thresholds, emergency sourcing, supplier escalation, cold-chain guidance, "
        "and other policy questions. Do not use for operational data analysis or "
        "DataRobot shortage probabilities."
    ),
)
