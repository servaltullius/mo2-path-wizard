import unittest

from mo2_path_wizard import qtini

# 기대값은 PySide6(Qt 6.9) QSettings(IniFormat)가 실제로 기록한 결과다.
_QT_BYTEARRAY_CASES = (
    ("D:\\모드팩\\Stock Game", "@ByteArray(D:\\\\\\xeb\\xaa\\xa8\\xeb\\x93\\x9c\\xed\\x8c\\xa9\\\\Stock Game)"),
    ("G:\\Pack 1a\\é9F", "@ByteArray(G:\\\\Pack 1a\\\\\\xc3\\xa9\\x39\\x46)"),
    ("C:\\a,b;c\\x\"q", '"@ByteArray(C:\\\\a,b;c\\\\x\\"q)"'),
    ("D:\\éa", "@ByteArray(D:\\\\\\xc3\\xa9\\x61)"),
    ("C:\\Users\\RUNNER~1", "@ByteArray(C:\\\\Users\\\\RUNNER~1)"),
)
_QT_STRING_CASES = (
    ("D:\\모드팩\\Stock Game", "D:\\\\모드팩\\\\Stock Game"),
    ("C:\\a,b;c\\x\"q", '"C:\\\\a,b;c\\\\x\\"q"'),
    ("G:/TAKEALOOK/Stock Game", "G:/TAKEALOOK/Stock Game"),
)


class TestQtIni(unittest.TestCase):
    def test_bytearray_encoding_matches_qt(self) -> None:
        for path, expected in _QT_BYTEARRAY_CASES:
            with self.subTest(path=path):
                self.assertEqual(expected, qtini.encode_bytearray(path.encode("utf-8")))

    def test_bytearray_decoding_matches_qt(self) -> None:
        for path, raw in _QT_BYTEARRAY_CASES:
            with self.subTest(path=path):
                self.assertEqual(path, qtini.decode_path_bytearray(raw))

    def test_string_round_trip_matches_qt(self) -> None:
        for value, raw in _QT_STRING_CASES:
            with self.subTest(value=value):
                self.assertEqual(raw, qtini.escape_string(value))
                self.assertEqual(value, qtini.unescape_string(raw))

    def test_decodes_legacy_raw_utf8_bytearray(self) -> None:
        # v1.0.7 이하가 기록한 형식(UTF-8 원문)도 읽을 수 있어야 한다.
        self.assertEqual("D:\\모드팩\\Stock Game", qtini.decode_path_bytearray("@ByteArray(D:\\\\모드팩\\\\Stock Game)"))

    def test_non_bytearray_returns_none(self) -> None:
        self.assertIsNone(qtini.decode_path_bytearray("D:/Pack"))


if __name__ == "__main__":
    unittest.main()
