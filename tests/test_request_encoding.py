"""The astra_tool request must be decoded as UTF-8, not the Windows locale.

Regression test for the codex_cli/agy_cli "'utf-8' codec can't encode character
'\\udc81' ... surrogates not allowed" failure seen in the research-trajectory
pilot. Root cause: a child launched without PYTHONIOENCODING inherits
cp1252+surrogateescape on sys.stdin, so UTF-8 bytes 0x81/0x9D inside multi-byte
sequences become lone surrogates that later crash prompt encoding. The runner
sends UTF-8, so astra_tool must decode UTF-8.
"""
import io
import json
import unittest

from astra_tool import _read_request


def _has_surrogate(s):
    return isinstance(s, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in s)


# U+0081 -> UTF-8 "C2 81" and U+009D -> UTF-8 "C2 9D": these embed the exact
# bytes (0x81, 0x9D) that are undefined in cp1252 and became \udc81/\udc9d in the
# pilot. Real accumulated model output carries them inside multi-byte sequences;
# these code points are the minimal reproduction.
B81 = chr(0x81)
B9D = chr(0x9D)


class RequestEncoding(unittest.TestCase):
    def test_utf8_request_with_0x81_0x9d_bytes_has_no_surrogates(self):
        original = {
            "action": "cycle",
            "axiomatic_base": "prior " + B81 + " result end " + B9D + " cafe",
            "thread_summary": "cycle 3 " + B81 + " refuted",
        }
        payload = json.dumps(original, ensure_ascii=False).encode("utf-8")
        self.assertIn(0x81, payload)
        self.assertIn(0x9D, payload)

        req = _read_request(io.BytesIO(payload))

        for key, value in req.items():
            self.assertFalse(_has_surrogate(value), f"{key} carries a surrogate")
        # Content round-trips exactly as UTF-8.
        self.assertEqual(req["axiomatic_base"], original["axiomatic_base"])
        self.assertEqual(req["thread_summary"], original["thread_summary"])

    def test_locale_path_would_have_corrupted_it(self):
        # Proves the fix addresses a real defect: decoding the SAME UTF-8 bytes
        # the way an unconfigured Windows child does (cp1252+surrogateescape)
        # yields exactly the lone surrogates from the pilot error.
        payload = json.dumps({"x": B81 + B9D}, ensure_ascii=False).encode("utf-8")
        corrupted = payload.decode("cp1252", errors="surrogateescape")
        surrogates = {hex(ord(c)) for c in corrupted if 0xD800 <= ord(c) <= 0xDFFF}
        self.assertEqual(surrogates, {"0xdc81", "0xdc9d"})

    def test_invalid_bytes_never_yield_a_surrogate(self):
        # Even raw undecodable bytes (not valid UTF-8) must become U+FFFD, never a
        # lone surrogate that would crash a later utf-8 encode.
        raw = b'{"x": "a' + bytes([0x81, 0x9D]) + b'b"}'
        req = _read_request(io.BytesIO(raw))
        self.assertFalse(_has_surrogate(req["x"]))
        req["x"].encode("utf-8")  # must not raise (the pilot crash)


class OracleCaptureEncoding(unittest.IsolatedAsyncioTestCase):
    """The local oracle must capture the validator's stdout as UTF-8, so a
    validator that prints non-ASCII (Greek/maths symbols) never yields a lone
    surrogate that crashes a later prompt encode."""

    async def test_validator_nonascii_stdout_has_no_surrogates(self):
        import tempfile

        from core.executor import execute_python_code

        # ASCII source; the OUTPUT is U+0081 + U+009D (the cp1252-undefined bytes)
        # plus a Greek letter, mimicking a physics validator's stdout.
        code = "print(chr(0x81) + chr(0x9d) + '\\u0394 ok')"
        with tempfile.TemporaryDirectory() as tmp:
            result = await execute_python_code(code, workspace_dir=tmp, timeout=30)

        out = result.get("stdout") or ""
        self.assertFalse(
            any(0xD800 <= ord(c) <= 0xDFFF for c in out),
            "oracle stdout carries a lone surrogate",
        )
        out.encode("utf-8")  # must not raise (the pilot crash signature)
        self.assertIn("Δ", out)  # the Greek delta round-trips


if __name__ == "__main__":
    unittest.main()
