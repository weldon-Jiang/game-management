"""视觉解码与模板匹配模块。"""
from .frame_capture import VideoFrameCapture, Frame
from .template_matcher import TemplateMatcher, MatchResult

__all__ = ['VideoFrameCapture', 'Frame', 'TemplateMatcher', 'MatchResult']
