"""
pytest 配置和共享 fixtures

提供测试所需的 mock 对象和工具函数
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def call_counter():
    """
    创建一个调用计数器

    Returns:
        dict: 包含 'count' 键的字典，用于跟踪调用次数
    """
    return {'count': 0}


@pytest.fixture
def mock_sse_response_factory(call_counter):
    """
    创建 mock SSE 响应的工厂函数

    Args:
        call_counter: 调用计数器 fixture

    Returns:
        function: 创建 mock 响应的工厂函数
    """
    def create_response(responses):
        """
        创建 mock SSE 响应

        Args:
            responses: 响应列表，每个元素可以是：
                      - 字符串：返回该内容
                      - 异常对象：抛出该异常
                      例如：["", "actual content"] 或 [httpx.TimeoutException("timeout"), "success"]

        Returns:
            MagicMock: mock 的响应对象
        """
        async def mock_aiter_lines():
            """模拟 SSE 流式响应"""
            call_counter['count'] += 1
            current_call = call_counter['count']

            # 根据调用次数返回不同的响应
            if current_call <= len(responses):
                response_item = responses[current_call - 1]
            else:
                # 如果调用次数超过预期，返回最后一个响应
                response_item = responses[-1]

            # 如果是异常，抛出异常
            if isinstance(response_item, Exception):
                raise response_item

            # 否则返回内容
            content = response_item

            # 模拟 SSE 格式
            yield f'data: {{"choices":[{{"delta":{{"content":"{content}"}}}}]}}'
            yield 'data: [DONE]'

        mock_response = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = MagicMock()

        return mock_response

    return create_response


@pytest.fixture
def mock_http_client(mock_sse_response_factory):
    """
    创建 mock HTTP 客户端的工厂函数

    Args:
        mock_sse_response_factory: SSE 响应工厂 fixture

    Returns:
        function: 创建 mock 客户端的工厂函数
    """
    def create_client(responses):
        """
        创建 mock HTTP 客户端

        Args:
            responses: 响应列表，传递给 mock_sse_response_factory

        Returns:
            patch: httpx.AsyncClient 的 patch 对象
        """
        mock_response = mock_sse_response_factory(responses)

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_stream_context)

        mock_client_context = AsyncMock()
        mock_client_context.__aenter__.return_value = mock_client
        mock_client_context.__aexit__.return_value = None

        return patch('httpx.AsyncClient', return_value=mock_client_context)

    return create_client


@pytest.fixture
def provider():
    """
    创建 GrokSearchProvider 实例

    Returns:
        GrokSearchProvider: provider 实例
    """
    from grok_search.providers.grok import GrokSearchProvider
    return GrokSearchProvider("http://test-api.com", "test-key", "test-model")
