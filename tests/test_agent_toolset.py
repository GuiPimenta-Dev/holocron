"""Toolset restriction guard: unknown names fail fast, before any resource is touched.

Only the pure validation is tested — agent behavior is measured by eval runs
(testing doctrine), and TOOL_NAMES drift is asserted inside _bind_tools itself.
"""

from typing import Any, cast

import pytest

from agent.holocron import TOOL_NAMES, HolocronAgent


def test_tool_names_cover_the_known_tools():
    assert TOOL_NAMES == frozenset({"get_entity", "get_relations", "search_chunks", "path_between", "run_cypher"})


def test_unknown_toolset_name_rejected():
    with pytest.raises(ValueError, match="unknown tool"):
        HolocronAgent(
            graph=cast(Any, None),  # validation raises before resources are used
            index=cast(Any, None),
            traced=False,
            toolset=frozenset({"search_chunks", "use_the_force"}),
        )
