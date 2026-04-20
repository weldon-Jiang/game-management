"""
Template manager for Bend Agent
Downloads and caches templates from the platform
"""
import asyncio
import aiohttp
import os
import hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import config
from ..core.logger import get_logger


@dataclass
class TemplateInfo:
    """Template information"""
    id: str
    name: str
    description: str
    category: str
    image_url: str
    local_path: str
    width: int
    height: int
    match_threshold: float
    game: str
    checksum: str
    last_updated: datetime


class TemplateManager:
    """
    Template manager for downloading and caching templates from platform
    """

    def __init__(self):
        self.logger = get_logger('template')
        self._templates: Dict[str, TemplateInfo] = {}
        self._cache_dir = config.get('agent.template_cache_dir',
            os.path.join(os.environ.get('APPDATA', ''), 'BendPlatform', 'Agent', 'templates'))
        os.makedirs(self._cache_dir, exist_ok=True)
        self._base_url = config.backend_url

    async def sync_templates(self, categories: List[str] = None) -> int:
        """
        Sync templates from platform

        Args:
            categories: List of categories to sync (None = all)

        Returns:
            Number of templates synced
        """
        self.logger.info("Starting template sync...")

        try:
            templates = await self._fetch_template_list(categories)
            synced = 0

            for template_data in templates:
                if await self._download_template(template_data):
                    synced += 1

            self.logger.info(f"Template sync completed: {synced}/{len(templates)} templates")
            return synced

        except Exception as e:
            self.logger.error(f"Template sync failed: {e}")
            return 0

    async def _fetch_template_list(self, categories: List[str] = None) -> List[Dict]:
        """Fetch template list from platform"""
        try:
            url = f"{self._base_url}{config.get('backend.api_prefix', '/api')}/templates"
            params = {}
            if categories:
                params['category'] = ','.join(categories)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('code') == 0:
                            return result.get('data', [])
                    return []
        except Exception as e:
            self.logger.error(f"Failed to fetch template list: {e}")
            return []

    async def _download_template(self, template_data: Dict) -> bool:
        """
        Download a single template

        Args:
            template_data: Template data from API

        Returns:
            True if downloaded successfully
        """
        try:
            template_id = template_data.get('id')
            image_url = template_data.get('imageUrl')

            if not image_url:
                return False

            local_filename = f"{template_id}.png"
            local_path = os.path.join(self._cache_dir, local_filename)

            if os.path.exists(local_path):
                existing_checksum = self._calculate_file_checksum(local_path)
                if existing_checksum == template_data.get('checksum'):
                    self.logger.debug(f"Template {template_id} already cached")
                    self._templates[template_id] = self._create_template_info(template_data, local_path)
                    return True

            download_url = f"{self._base_url}{image_url}"
            success = await self._download_file(download_url, local_path)

            if success:
                self._templates[template_id] = self._create_template_info(template_data, local_path)
                self.logger.info(f"Downloaded template: {template_data.get('name')}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to download template {template_data.get('id')}: {e}")
            return False

    async def _download_file(self, url: str, dest_path: str) -> bool:
        """Download file from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(dest_path, 'wb') as f:
                            f.write(content)
                        return True
                    return False
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False

    def _create_template_info(self, data: Dict, local_path: str) -> TemplateInfo:
        """Create TemplateInfo from data"""
        return TemplateInfo(
            id=data.get('id'),
            name=data.get('name'),
            description=data.get('description', ''),
            category=data.get('category', 'other'),
            image_url=data.get('imageUrl', ''),
            local_path=local_path,
            width=data.get('width', 0),
            height=data.get('height', 0),
            match_threshold=data.get('matchThreshold', 0.8),
            game=data.get('game', 'other'),
            checksum=data.get('checksum', ''),
            last_updated=datetime.now()
        )

    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ''

    def get_template(self, template_id: str) -> Optional[TemplateInfo]:
        """Get template by ID"""
        return self._templates.get(template_id)

    def get_templates_by_category(self, category: str) -> List[TemplateInfo]:
        """Get all templates in a category"""
        return [t for t in self._templates.values() if t.category == category]

    def get_templates_by_game(self, game: str) -> List[TemplateInfo]:
        """Get all templates for a game"""
        return [t for t in self._templates.values() if t.game == game]

    def get_all_templates(self) -> List[TemplateInfo]:
        """Get all cached templates"""
        return list(self._templates.values())

    def get_local_path(self, template_id: str) -> Optional[str]:
        """Get local file path for a template"""
        template = self._templates.get(template_id)
        if template and os.path.exists(template.local_path):
            return template.local_path
        return None

    async def delete_template(self, template_id: str) -> bool:
        """Delete a cached template"""
        template = self._templates.get(template_id)
        if template and os.path.exists(template.local_path):
            try:
                os.remove(template.local_path)
                del self._templates[template_id]
                self.logger.info(f"Deleted template: {template_id}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to delete template: {e}")
        return False

    def clear_cache(self):
        """Clear all cached templates"""
        for template in self._templates.values():
            try:
                if os.path.exists(template.local_path):
                    os.remove(template.local_path)
            except Exception:
                pass
        self._templates.clear()
        self.logger.info("Template cache cleared")


template_manager = TemplateManager()
