"""
최적화된 API 클라이언트 유틸리티
"""
import aiohttp
import asyncio
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
import logging
from .config import config
from .errors import APIError, BotError, redact_secrets

logger = logging.getLogger(__name__)

class OptimizedAPIClient:
    """최적화된 API 클라이언트"""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_times: OrderedDict[str, datetime] = OrderedDict()
        self._max_cache_size = 1000
        self._semaphore = asyncio.Semaphore(10)  # 동시 요청 제한
        
    async def get_session(self) -> aiohttp.ClientSession:
        """세션을 가져오거나 생성합니다."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                limit=100,  # 총 연결 수 제한
                limit_per_host=30,  # 호스트당 연결 수 제한
                ttl_dns_cache=300,  # DNS 캐시 TTL
                use_dns_cache=True,
            )
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'x-api-key': config.api_key}
            )
        return self._session
    
    async def close(self):
        """세션을 닫습니다."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def _get_cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        """캐시 키를 생성합니다."""
        if params:
            sorted_params = sorted(params.items())
            param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
            return f"{url}?{param_str}"
        return url
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시가 유효한지 확인합니다."""
        if cache_key not in self._cache:
            return False
        
        cache_time = self._cache_times.get(cache_key)
        if not cache_time:
            return False
        
        return datetime.now() - cache_time < timedelta(seconds=config.cache_ttl)
    
    def _set_cache(self, cache_key: str, data: Any):
        """캐시를 설정합니다. (LRU)"""
        # 기존 키가 있으면 삭제 (재정렬을 위해)
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._cache_times[cache_key]

        # 새로 추가 (OrderedDict의 끝에 추가됨)
        self._cache[cache_key] = data
        self._cache_times[cache_key] = datetime.now()

        # 캐시 크기 제한 (LRU - 가장 오래된 항목 제거)
        if len(self._cache) > self._max_cache_size:
            # OrderedDict의 첫 번째 항목이 가장 오래된 항목
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._cache_times[oldest_key]
    
    async def get(self, url: str, params: Optional[Dict] = None, use_cache: bool = True, _retry_count: int = 0) -> Dict[str, Any]:
        """GET 요청을 수행합니다."""
        MAX_RETRIES = 3

        cache_key = self._get_cache_key(url, params)

        # 캐시 확인
        if use_cache and self._is_cache_valid(cache_key):
            # LRU: 최근 사용 항목으로 이동
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        # 세마포어를 사용하여 동시 요청 제한
        async with self._semaphore:
            session = await self.get_session()

            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if use_cache:
                            self._set_cache(cache_key, data)
                        return data
                    elif response.status == 429:
                        if _retry_count >= MAX_RETRIES:
                            raise APIError(
                                f"API Rate limit 초과 (최대 {MAX_RETRIES}회 재시도 후 실패)",
                                "API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
                            )
                        retry_after = int(response.headers.get('Retry-After', config.retry_delay))
                        logger.warning(f"API Rate limit - {retry_after}초 대기 (재시도 {_retry_count + 1}/{MAX_RETRIES})")
                        await asyncio.sleep(retry_after)
                        return await self.get(url, params, use_cache, _retry_count + 1)
                    else:
                        error_text = await response.text()
                        logger.error(f"API 요청 실패: {response.status}")
                        raise APIError(
                            f"API 요청 실패: {response.status} - {error_text}",
                            "API 요청 중 오류가 발생했습니다."
                        )
            except aiohttp.ClientError as e:
                logger.error(f"네트워크 오류: {redact_secrets(e)}")
                raise APIError(f"네트워크 오류: {redact_secrets(e)}", "네트워크 연결 중 오류가 발생했습니다.")
            except Exception as e:
                logger.error(f"예상치 못한 오류: {redact_secrets(e)}")
                raise BotError(f"예상치 못한 오류: {redact_secrets(e)}", "서버 오류가 발생했습니다.")
    
    async def batch_get(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """여러 요청을 배치로 처리합니다."""
        async def single_request(req_data: Dict[str, Any]) -> Dict[str, Any]:
            url = req_data['url']
            params = req_data.get('params')
            use_cache = req_data.get('use_cache', True)
            return await self.get(url, params, use_cache)
        
        # 동시에 여러 요청 실행
        tasks = [single_request(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 요청 실패: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    def clear_cache(self):
        """캐시를 초기화합니다."""
        self._cache.clear()
        self._cache_times.clear()
        # 캐시 초기화 로그 제거 (불필요한 정보)

# 전역 API 클라이언트 인스턴스
api_client = OptimizedAPIClient()
