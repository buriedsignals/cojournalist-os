"""
Tests for embedding_utils.

Verifies:
1. Embedding compression/decompression roundtrip
2. Cosine similarity calculation
3. normalize_embedding
4. generate_embedding (Gemini API format)
5. generate_embedding_multimodal
"""
import base64
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.services.embedding_utils import (
    cosine_similarity,
    compress_embedding,
    decompress_embedding,
    normalize_embedding,
    generate_embedding,
    generate_embedding_multimodal,
    generate_embeddings_batch,
)


class TestEmbeddingCompression:
    """Test embedding compress/decompress roundtrip."""

    def test_roundtrip(self):
        original = [0.1, 0.2, 0.3, -0.5, 1.0]
        compressed = compress_embedding(original)
        decompressed = decompress_embedding(compressed)
        assert len(decompressed) == len(original)
        for a, b in zip(original, decompressed):
            assert abs(a - b) < 1e-6

    def test_compressed_is_base64(self):
        compressed = compress_embedding([0.1, 0.2])
        # Should be valid base64
        base64.b64decode(compressed)


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestNormalizeEmbedding:
    """Test normalize_embedding function."""

    def test_unit_vector_unchanged(self):
        # A vector already at unit length should remain at unit length
        v = [1.0, 0.0, 0.0]
        result = normalize_embedding(v)
        norm = sum(x * x for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_normalizes_to_unit_length(self):
        v = [3.0, 4.0]  # norm = 5.0
        result = normalize_embedding(v)
        norm = sum(x * x for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_zero_vector_returned_unchanged(self):
        v = [0.0, 0.0, 0.0]
        result = normalize_embedding(v)
        assert result == v

    def test_returns_list_of_floats(self):
        v = [1.0, 2.0, 3.0]
        result = normalize_embedding(v)
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_normalized_vectors_cosine_similarity_one(self):
        v = [1.0, 2.0, 3.0]
        norm_v = normalize_embedding(v)
        # Cosine similarity of normalized vector with itself should be 1
        assert abs(cosine_similarity(norm_v, norm_v) - 1.0) < 1e-6


class TestGenerateEmbedding:
    """Test generate_embedding function with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_returns_normalized_embedding_on_success(self):
        """generate_embedding should return normalized floats from Gemini response."""
        mock_values = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embedding": {"values": mock_values}
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            result = await generate_embedding("test text", "SEMANTIC_SIMILARITY")
            assert isinstance(result, list)
            assert len(result) == 3
            # Result should be normalized
            norm = sum(x * x for x in result) ** 0.5
            assert abs(norm - 1.0) < 1e-6
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_raises_on_non_200(self):
        """generate_embedding should raise an exception on non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            with pytest.raises(Exception, match="Embedding failed"):
                await generate_embedding("test text")
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_applies_query_prefix_in_request(self):
        """generate_embedding should encode retrieval intent in the text payload."""
        mock_values = [1.0, 0.0]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            await generate_embedding("hello", "RETRIEVAL_QUERY")
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"]
            assert payload["content"]["parts"][0]["text"] == "task: search result | query: hello"
            assert "taskType" not in payload
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_applies_document_title_prefix_in_request(self):
        """RETRIEVAL_DOCUMENT should include title metadata in the text payload."""
        mock_values = [1.0, 0.0]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            await generate_embedding("body text", "RETRIEVAL_DOCUMENT", title="Council Minutes")
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"]
            assert payload["content"]["parts"][0]["text"] == (
                "title: Council Minutes | text: body text"
            )
            assert "taskType" not in payload
        finally:
            eu.get_http_client = original


class TestGenerateEmbeddingMultimodal:
    """Test generate_embedding_multimodal function."""

    @pytest.mark.asyncio
    async def test_text_only_succeeds(self):
        """Multimodal embedding with text only should succeed."""
        mock_values = [0.5, 0.5]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            result = await generate_embedding_multimodal(text="hello world")
            assert isinstance(result, list)
            assert len(result) == 2
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_image_only_succeeds(self):
        """Multimodal embedding with image bytes only should succeed."""
        mock_values = [0.3, 0.7]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            result = await generate_embedding_multimodal(image_bytes=b"\xff\xd8\xff")
            assert isinstance(result, list)
            assert len(result) == 2
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_raises_when_no_input(self):
        """Should raise ValueError if neither text nor image_bytes is provided."""
        with pytest.raises(ValueError, match="At least one of text or image_bytes"):
            await generate_embedding_multimodal()

    @pytest.mark.asyncio
    async def test_image_encoded_as_base64_in_request(self):
        """Image bytes should be base64-encoded in the request payload."""
        mock_values = [0.1, 0.9]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        image_data = b"\xff\xd8\xff\xe0"
        expected_b64 = base64.standard_b64encode(image_data).decode("utf-8")

        try:
            await generate_embedding_multimodal(image_bytes=image_data, mime_type="image/jpeg")
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"]
            parts = payload["content"]["parts"]
            inline_part = next(p for p in parts if "inline_data" in p)
            assert inline_part["inline_data"]["data"] == expected_b64
            assert inline_part["inline_data"]["mime_type"] == "image/jpeg"
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_text_prefix_applied_when_text_present(self):
        """Multimodal embedding should prefix the text part when text is present."""
        mock_values = [0.1, 0.9]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": {"values": mock_values}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            await generate_embedding_multimodal(
                text="caption",
                image_bytes=b"\xff\xd8\xff",
                task_type="RETRIEVAL_DOCUMENT",
                title="Weekly digest",
            )
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"]
            text_part = next(p for p in payload["content"]["parts"] if "text" in p)
            assert text_part["text"] == "title: Weekly digest | text: caption"
            assert "taskType" not in payload
        finally:
            eu.get_http_client = original


class TestGenerateEmbeddingsBatch:
    """Test batch embedding request formatting."""

    @pytest.mark.asyncio
    async def test_batch_applies_titles_for_retrieval_documents(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [{"values": [1.0, 0.0]}, {"values": [0.0, 1.0]}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client = AsyncMock(return_value=mock_client)

        import app.services.embedding_utils as eu
        original = eu.get_http_client
        eu.get_http_client = mock_get_client

        try:
            await generate_embeddings_batch(
                ["alpha", "beta"],
                "RETRIEVAL_DOCUMENT",
                titles=["Title A", None],
            )
            payload = mock_client.post.call_args[1]["json"]
            requests = payload["requests"]
            assert requests[0]["content"]["parts"][0]["text"] == "title: Title A | text: alpha"
            assert requests[1]["content"]["parts"][0]["text"] == "title: none | text: beta"
            assert all("taskType" not in request for request in requests)
        finally:
            eu.get_http_client = original

    @pytest.mark.asyncio
    async def test_batch_raises_when_titles_length_mismatches(self):
        with pytest.raises(ValueError, match="titles must be the same length as texts"):
            await generate_embeddings_batch(["alpha"], titles=["one", "two"])
