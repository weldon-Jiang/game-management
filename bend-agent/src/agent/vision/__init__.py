"""
Vision module initialization
"""
from .frame_capture import VideoFrameCapture, Frame
from .template_matcher import TemplateMatcher, MatchResult

__all__ = ['VideoFrameCapture', 'Frame', 'TemplateMatcher', 'MatchResult']
