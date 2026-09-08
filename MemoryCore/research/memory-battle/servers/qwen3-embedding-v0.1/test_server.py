import unittest
from io import BytesIO

from server import handler_for, normalize_inputs


class FailingRuntime:
    model_id = "test-model"

    def __init__(self):
        self.requests = 0
        self.failures = 0

    def request_received(self):
        self.requests += 1

    def failure(self):
        self.failures += 1


class NormalizeInputsTest(unittest.TestCase):
    def test_string_becomes_singleton(self):
        self.assertEqual(normalize_inputs("hello"), ["hello"])

    def test_string_array_is_preserved(self):
        self.assertEqual(normalize_inputs(["a", "b"]), ["a", "b"])

    def test_non_string_rejected(self):
        with self.assertRaises(ValueError):
            normalize_inputs(["a", 2])

    def test_failed_embedding_attempt_is_counted_as_request(self):
        runtime = FailingRuntime()
        handler_class = handler_for(runtime)
        handler = handler_class.__new__(handler_class)
        handler.path = "/v1/embeddings"
        handler.headers = {"Content-Length": "2"}
        handler.rfile = BytesIO(b"{}")
        handler.wfile = BytesIO()
        handler.request_version = "HTTP/1.1"
        handler.command = "POST"
        handler.requestline = "POST /v1/embeddings HTTP/1.1"
        handler.do_POST()
        self.assertIn(b"400 Bad Request", handler.wfile.getvalue())
        self.assertEqual(runtime.requests, 1)
        self.assertEqual(runtime.failures, 1)


if __name__ == "__main__":
    unittest.main()
