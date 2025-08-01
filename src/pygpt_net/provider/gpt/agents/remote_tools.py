#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# Created By  : Marcin Szczygliński                  #
# Updated Date: 2025.07.30 00:00:00                  #
# ================================================== #

import json

from agents import (
    WebSearchTool,
    CodeInterpreterTool,
    ImageGenerationTool,
    FileSearchTool,
    ComputerTool,
    HostedMCPTool,
)

from pygpt_net.core.types import (
    OPENAI_REMOTE_TOOL_DISABLE_CODE_INTERPRETER,
    OPENAI_REMOTE_TOOL_DISABLE_COMPUTER_USE,
    OPENAI_REMOTE_TOOL_DISABLE_IMAGE,
    OPENAI_REMOTE_TOOL_DISABLE_WEB_SEARCH,
    OPENAI_REMOTE_TOOL_DISABLE_FILE_SEARCH,
    OPENAI_REMOTE_TOOL_DISABLE_MCP,
)
from pygpt_net.item.model import ModelItem
from pygpt_net.item.preset import PresetItem

from .computer import LocalComputer


def is_computer_tool(
        window,
        model: ModelItem,
        preset: PresetItem,
        is_expert_call: bool,
):
    if not model.is_gpt():
        return False

    if not is_expert_call:
        # from global config if not expert call
        return model.id.startswith("computer-use")
    else:
        # for expert call, get from preset config
        if preset and preset.remote_tools:
            tools_list = [preset_remote_tool.strip() for preset_remote_tool in preset.remote_tools.split(",") if
                          preset_remote_tool.strip()]
            return "computer_use" in tools_list and model.id.startswith("computer-use")

def get_remote_tools(
        window,
        model: ModelItem,
        preset: PresetItem,
        is_expert_call: bool,
):
    """
    Append remote tools to the list based on the model and preset configuration.

    :param model: ModelItem instance
    :param preset: PresetItem instance
    :param is_expert_call: Flag indicating if it's an expert call
    :param window: Window instance
    """
    tools = []

    if not model.is_gpt():
        return []

    def on_safety_check(data):
        """
        Safety check for the computer tool.
        """
        return True

    # disabled by default
    enabled = {
        "web_search": False,
        "image": False,
        "code_interpreter": False,
        "mcp": False,
        "file_search": False,
        "computer_use": False,
    }

    # from global config if not expert call
    if not is_expert_call:
        enabled["web_search"] = window.core.config.get("remote_tools.web_search", False)
        enabled["image"] = window.core.config.get("remote_tools.image", False)
        enabled["code_interpreter"] = window.core.config.get("remote_tools.code_interpreter", False)
        enabled["mcp"] = window.core.config.get("remote_tools.mcp", False)
        enabled["file_search"] = window.core.config.get("remote_tools.file_search", False)
        enabled["computer_use"] = model.id.startswith("computer-use")
    else:
        # for expert call, get from preset config
        if preset:
            if preset.remote_tools:
                tools_list = [preset_remote_tool.strip() for preset_remote_tool in preset.remote_tools.split(",") if
                              preset_remote_tool.strip()]
                for item in tools_list:
                    if item in enabled:
                        enabled[item] = True

    if enabled["computer_use"]:
        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_COMPUTER_USE:
            computer = LocalComputer(window=window)
            tools.append(ComputerTool(computer, on_safety_check=on_safety_check))
    else:
        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_WEB_SEARCH:
            if enabled["web_search"]:
                tools.append(WebSearchTool())

        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_CODE_INTERPRETER:
            if enabled["code_interpreter"]:
                tools.append(CodeInterpreterTool(
                    tool_config={"type": "code_interpreter", "container": {"type": "auto"}},
                ))

        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_IMAGE:
            if enabled["image"]:
                tools.append(ImageGenerationTool(
                    tool_config={"type": "image_generation", "quality": "low"},
                ))

        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_FILE_SEARCH:
            if enabled["file_search"]:
                vector_store_ids = window.core.config.get("remote_tools.file_search.args", "")
                if vector_store_ids:
                    vector_store_ids = [store.strip() for store in vector_store_ids.split(",") if store.strip()]
                tools.append(FileSearchTool(
                    max_num_results=3,
                    vector_store_ids=vector_store_ids,
                    include_search_results=True,
                ))

        if not model.id in OPENAI_REMOTE_TOOL_DISABLE_MCP:
            if enabled["mcp"]:
                mcp_tool = window.core.config.get("remote_tools.mcp.args", "")
                if mcp_tool:
                    mcp_tool = json.loads(mcp_tool)
                    tools.append(HostedMCPTool(
                        tool_config=mcp_tool,
                    ))

    return tools
