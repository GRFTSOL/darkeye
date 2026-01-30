import pytest,sys,os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph.text_parser import parse_wikilinks, extract_references

class TestWikiLinkParser:
    
    def test_basic_link(self):
        """测试基本的 [[Target]] 格式"""
        text = "这是一个 [[SNIS-123]] 的测试"
        result = parse_wikilinks(text)
        assert len(result) == 1
        assert result[0] == ("SNIS-123", None)

    def test_alias_link(self):
        """测试带别名的 [[Target|Alias]] 格式"""
        text = "这是一个 [[SNIS-123|神作]] 的测试"
        result = parse_wikilinks(text)
        assert len(result) == 1
        assert result[0] == ("SNIS-123", "神作")

    def test_multiple_links(self):
        """测试多个混合链接"""
        text = "推荐 [[SNIS-123]] 和 [[SNIS-456|续作]]，还有 [[SSIS-789]]"
        result = parse_wikilinks(text)
        assert len(result) == 3
        assert result[0] == ("SNIS-123", None)
        assert result[1] == ("SNIS-456", "续作")
        assert result[2] == ("SSIS-789", None)

    def test_empty_input(self):
        """测试空输入"""
        assert parse_wikilinks("") == []
        assert parse_wikilinks(None) == []

    def test_no_links(self):
        """测试无链接文本"""
        text = "这段文字没有任何链接"
        assert parse_wikilinks(text) == []

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        text = " [[  SNIS-123  ]] 和 [[  SNIS-456  |  别名  ]] "
        result = parse_wikilinks(text)
        assert result[0] == ("SNIS-123", None)
        assert result[1] == ("SNIS-456", "别名")

    def test_special_characters(self):
        """测试特殊字符（如中文番号、含符号的别名）"""
        text = "[[FC2-PPV-123456]] [[作品 A|这是|一个|别名]]"
        result = parse_wikilinks(text)
        assert result[0] == ("FC2-PPV-123456", None)
        # 确保只分割了第一个竖线
        assert result[1] == ("作品 A", "这是|一个|别名")

    def test_extract_references_deduplication(self):
        """测试引用提取的去重功能"""
        text = "[[A]] [[B]] [[A|Alias]] [[C]]"
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs == {"A", "B", "C"}
