import os
import shutil
import yt_dlp
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class VideoProcessor:
    """媒体处理器，使用yt-dlp下载并转换音频"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',  # 优先下载最佳音频源
            'outtmpl': '%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                # 直接在提取阶段转换为单声道 16k（空间小且稳定）
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            # 全局FFmpeg参数：单声道 + 16k 采样率 + faststart
            'postprocessor_args': ['-ac', '1', '-ar', '16000', '-movflags', '+faststart'],
            'prefer_ffmpeg': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,  # 强制只下载单个视频，不下载播放列表
        }
        self.ffmpeg_path = self._detect_binary("ffmpeg")
        self.ffprobe_path = self._detect_binary("ffprobe")
        if not self.ffprobe_path and self.ffmpeg_path:
            sibling_probe = Path(self.ffmpeg_path).with_name("ffprobe")
            if sibling_probe.exists():
                self.ffprobe_path = str(sibling_probe)

        if self.ffmpeg_path:
            # yt-dlp会同时寻找ffmpeg与ffprobe，同目录即可
            self.ydl_opts['ffmpeg_location'] = str(Path(self.ffmpeg_path).parent)
        else:
            logger.warning("未显式找到ffmpeg，可执行文件需在PATH中")
    
    async def download_and_convert(self, url: str, output_dir: Path) -> Tuple[str, str, Dict[str, Any]]:
        """
        下载媒体并转换为m4a格式
        
        Args:
            url (str): 视频或音频链接。
            output_dir (Path): 输出目录。
            
        Returns:
            Tuple[str, str, Dict[str, Any]]: (音频文件路径, 标题, 视频/音频信息字典)。

        Raises:
            Exception: 当下载或转换失败时抛出。
        """
        try:
            # 创建输出目录
            output_dir.mkdir(exist_ok=True)
            
            # 生成唯一的文件名
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            output_template = str(output_dir / f"audio_{unique_id}.%(ext)s")
            
            # 更新yt-dlp选项
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['outtmpl'] = output_template
            
            logger.info(f"开始下载媒体: {url}")
            
            # 直接同步执行，不使用线程池
            # 在FastAPI中，IO密集型操作可以直接await
            import asyncio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 获取媒体信息（放到线程池避免阻塞事件循环）
                info = await asyncio.to_thread(ydl.extract_info, url, False)
                video_title = info.get('title', 'unknown')
                expected_duration = info.get('duration') or 0
                logger.info(f"媒体标题: {video_title}")
                
                # 下载媒体（放到线程池避免阻塞事件循环）
                await asyncio.to_thread(ydl.download, [url])
            
            # 查找生成的m4a文件
            audio_file = str(output_dir / f"audio_{unique_id}.m4a")
            
            if not os.path.exists(audio_file):
                # 如果m4a文件不存在，查找其他音频格式
                for ext in ['webm', 'mp4', 'mp3', 'wav']:
                    potential_file = str(output_dir / f"audio_{unique_id}.{ext}")
                    if os.path.exists(potential_file):
                        audio_file = potential_file
                        break
                else:
                    raise Exception("未找到下载的音频文件")
            
            # 校验时长，如果和源视频差异较大，尝试一次ffmpeg规范化重封装
            try:
                import subprocess, shlex
                probe_binary = shlex.quote(self.ffprobe_path or "ffprobe")
                probe_cmd = f"{probe_binary} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {shlex.quote(audio_file)}"
                out = subprocess.check_output(probe_cmd, shell=True).decode().strip()
                actual_duration = float(out) if out else 0.0
            except Exception as _:
                actual_duration = 0.0
            
            if expected_duration and actual_duration and abs(actual_duration - expected_duration) / expected_duration > 0.1:
                logger.warning(
                    f"音频时长异常，期望{expected_duration}s，实际{actual_duration}s，尝试重封装修复…"
                )
                try:
                    fixed_path = str(output_dir / f"audio_{unique_id}_fixed.m4a")
                    ffmpeg_binary = shlex.quote(self.ffmpeg_path or "ffmpeg")
                    fix_cmd = f"{ffmpeg_binary} -y -i {shlex.quote(audio_file)} -vn -c:a aac -b:a 160k -movflags +faststart {shlex.quote(fixed_path)}"
                    subprocess.check_call(fix_cmd, shell=True)
                    # 用修复后的文件替换
                    audio_file = fixed_path
                    # 重新探测
                    probe_cmd_fixed = f"{probe_binary} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {shlex.quote(audio_file)}"
                    out2 = subprocess.check_output(probe_cmd_fixed, shell=True).decode().strip()
                    actual_duration2 = float(out2) if out2 else 0.0
                    logger.info(f"重封装完成，新时长≈{actual_duration2:.2f}s")
                except Exception as e:
                    logger.error(f"重封装失败：{e}")
            
            logger.info(f"音频文件已保存: {audio_file}")
            return audio_file, video_title, info
            
        except Exception as e:
            logger.error(f"下载视频失败: {str(e)}")
            raise Exception(f"下载视频失败: {str(e)}")
    
    def get_video_info(self, url: str) -> dict:
        """
        获取视频信息
        
        Args:
            url: 视频链接
            
        Returns:
            视频信息字典

        Raises:
            Exception: 当信息获取失败时抛出。
        """
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'upload_date': info.get('upload_date', ''),
                    'description': info.get('description', ''),
                    'view_count': info.get('view_count', 0),
                }
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            raise Exception(f"获取视频信息失败: {str(e)}")

    def _detect_binary(self, binary_name: str) -> Optional[str]:
        """
        自动探测指定可执行文件路径。

        Args:
            binary_name (str): 可执行文件名称。

        Returns:
            Optional[str]: 可执行文件路径。

        Raises:
            None.
        """
        candidates = [
            shutil.which(binary_name),
            f"/opt/homebrew/bin/{binary_name}",
            f"/usr/local/bin/{binary_name}",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None
