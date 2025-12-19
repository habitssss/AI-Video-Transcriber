from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import aiofiles
import uuid
import json
import re
from urllib.parse import urlparse

from video_processor import VideoProcessor
from transcriber import Transcriber
from summarizer import Summarizer
from translator import Translator
from media_source import MediaSource, resolve_media_source, AUDIO_EXTENSIONS
from podcast_resolver import resolve_podcast_episode

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI视频转录器", version="1.0.0")

# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")

# 创建临时目录
TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# 初始化处理器
video_processor = VideoProcessor()
transcriber = Transcriber()
summarizer = Summarizer()
translator = Translator()

# 存储任务状态 - 使用文件持久化
import threading

TASKS_FILE = TEMP_DIR / "tasks.json"
tasks_lock = threading.Lock()

def _current_timestamp() -> str:
    """
    获取当前UTC时间戳字符串。

    返回:
        str: ISO8601 格式的UTC时间戳。
    """
    return datetime.now(timezone.utc).isoformat()

def load_tasks() -> Dict[str, Any]:
    """
    加载任务状态。

    返回:
        Dict[str, Any]: 从磁盘读取的任务字典，读取失败时返回空字典。
    异常:
        无（内部捕获IO错误以保证服务启动）。
    """
    try:
        if TASKS_FILE.exists():
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_tasks(tasks_data: Dict[str, Any]) -> None:
    """
    将内存中的任务数据写入磁盘。

    参数:
        tasks_data (Dict[str, Any]): 需要持久化的任务字典。
    返回:
        None
    异常:
        无（内部记录错误日志，保持服务可用）。
    """
    try:
        with tasks_lock:
            temp_path = TASKS_FILE.with_suffix(".json.tmp")
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            temp_path.replace(TASKS_FILE)
    except Exception as e:
        logger.error(f"保存任务状态失败: {e}")

def _persist_task(task_id: str) -> Dict[str, Any]:
    """
    更新指定任务的更新时间并将所有任务写入磁盘。

    参数:
        task_id (str): 任务ID。
    返回:
        Dict[str, Any]: 更新后的任务数据。
    异常:
        KeyError: 当任务ID不存在时抛出。
    """
    if task_id not in tasks:
        raise KeyError(f"任务 {task_id} 不存在，无法持久化")
    tasks[task_id]["updated_at"] = _current_timestamp()
    save_tasks(tasks)
    return tasks[task_id]

def _ensure_task_metadata(task_id: str) -> Dict[str, Any]:
    """
    确保任务记录包含历史功能所需的元数据。

    参数:
        task_id (str): 任务ID。
    返回:
        Dict[str, Any]: 补全后的任务数据。
    异常:
        KeyError: 当任务ID不存在时抛出。
    """
    if task_id not in tasks:
        raise KeyError(f"任务 {task_id} 不存在，无法补全元数据")

    task = tasks[task_id]
    mutated = False

    if "created_at" not in task:
        task["created_at"] = task.get("updated_at") or _current_timestamp()
        mutated = True
    if "updated_at" not in task:
        task["updated_at"] = task["created_at"]
        mutated = True
    if task.get("status") == "completed" and not task.get("finished_at"):
        task["finished_at"] = task.get("updated_at")
        mutated = True
    if "has_translation" not in task:
        task["has_translation"] = bool(
            task.get("translation")
            or task.get("translation_path")
            or task.get("translation_filename")
        )
        mutated = True
    if "script_filename" not in task and task.get("script_path"):
        try:
            task["script_filename"] = Path(task["script_path"]).name
            mutated = True
        except Exception:
            logger.warning(f"无法解析脚本文件名: {task.get('script_path')}")
    if "summary_filename" not in task and task.get("summary_path"):
        try:
            task["summary_filename"] = Path(task["summary_path"]).name
            mutated = True
        except Exception:
            logger.warning(f"无法解析摘要文件名: {task.get('summary_path')}")
    if "translation_filename" not in task and task.get("translation_path"):
        try:
            task["translation_filename"] = Path(task["translation_path"]).name
            mutated = True
        except Exception:
            logger.warning(f"无法解析翻译文件名: {task.get('translation_path')}")

    if mutated:
        save_tasks(tasks)

    return task

def _validate_history_filename(filename: str) -> None:
    """
    校验待删除的历史文件名，确保不存在路径遍历风险。

    参数:
        filename (str): 需要校验的文件名。
    返回:
        None
    异常:
        HTTPException: 当文件名不合法时抛出400错误。
    """
    if not filename:
        return
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="文件名格式无效")

async def broadcast_task_update(task_id: str, task_data: dict):
    """向所有连接的SSE客户端广播任务状态更新"""
    logger.info(f"广播任务更新: {task_id}, 状态: {task_data.get('status')}, 连接数: {len(sse_connections.get(task_id, []))}")
    if task_id in sse_connections:
        connections_to_remove = []
        for queue in sse_connections[task_id]:
            try:
                await queue.put(json.dumps(task_data, ensure_ascii=False))
                logger.debug(f"消息已发送到队列: {task_id}")
            except Exception as e:
                logger.warning(f"发送消息到队列失败: {e}")
                connections_to_remove.append(queue)
        
        # 移除断开的连接
        for queue in connections_to_remove:
            sse_connections[task_id].remove(queue)
        
        # 如果没有连接了，清理该任务的连接列表
        if not sse_connections[task_id]:
            del sse_connections[task_id]

# 启动时加载任务状态
tasks = load_tasks()
# 存储正在处理的URL，防止重复处理
processing_urls = set()
# 存储活跃的任务对象，用于控制和取消
active_tasks = {}
# 存储SSE连接，用于实时推送状态更新
sse_connections = {}

def _sanitize_title_for_filename(title: str) -> str:
    """将视频标题清洗为安全的文件名片段。"""
    if not title:
        return "untitled"
    # 仅保留字母数字、下划线、连字符与空格
    safe = re.sub(r"[^\w\-\s]", "", title)
    # 压缩空白并转为下划线
    safe = re.sub(r"\s+", "_", safe).strip("._-")
    # 最长限制，避免过长文件名问题
    return safe[:80] or "untitled"

@app.get("/")
async def read_root():
    """返回前端页面"""
    return FileResponse(str(PROJECT_ROOT / "static" / "index.html"))

@app.post("/api/process-video")
async def process_video(
    url: str = Form(...),
    summary_language: str = Form(default="zh")
):
    """
    处理视频或播客链接，返回任务ID
    """
    try:
        # 检查是否已经在处理相同的URL
        if url in processing_urls:
            # 查找现有任务
            for tid, task in tasks.items():
                if task.get("url") == url:
                    return {"task_id": tid, "message": "该视频正在处理中，请等待..."}
            
        try:
            media_source = resolve_media_source(url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 标记URL为正在处理
        processing_urls.add(url)
        
        # 初始化任务状态
        timestamp_now = _current_timestamp()
        tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": f"开始处理{media_source.display_name}...",
            "script": None,
            "summary": None,
            "error": None,
            "url": url,  # 保存URL用于去重
            "created_at": timestamp_now,
            "updated_at": timestamp_now,
            "finished_at": None,
            "has_translation": False,
            "content_type": media_source.content_type,
            "provider": media_source.provider,
            "media_display_name": media_source.display_name
        }
        save_tasks(tasks)
        
        # 创建并跟踪异步任务
        task = asyncio.create_task(
            process_video_task(task_id, url, summary_language, media_source)
        )
        active_tasks[task_id] = task
        
        return {"task_id": task_id, "message": "任务已创建，正在处理中..."}
        
    except Exception as e:
        logger.error(f"处理视频时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

async def process_video_task(task_id: str, url: str, summary_language: str, media_source: MediaSource):
    """
    异步处理视频或播客任务。

    Args:
        task_id (str): 任务ID。
        url (str): 原始媒体链接。
        summary_language (str): 摘要目标语言。
        media_source (MediaSource): 解析后的媒体来源描述。

    Returns:
        None.

    Raises:
        Exception: 任意处理阶段失败时抛出并记录。
    """
    try:
        # 立即更新状态：开始下载媒体
        tasks[task_id].update({
            "status": "processing",
            "progress": 10,
            "message": f"正在下载{media_source.display_name}..."
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])
        
        # 添加短暂延迟确保状态更新
        import asyncio
        await asyncio.sleep(0.1)
        
        # 更新状态：正在解析媒体信息
        tasks[task_id].update({
            "progress": 15,
            "message": "正在解析媒体信息..."
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])

        resolved_url = url
        episode_info = None

        if media_source.content_type == "podcast":
            tasks[task_id].update({
                "progress": 18,
                "message": "正在解析播客音频..."
            })
            _persist_task(task_id)
            await broadcast_task_update(task_id, tasks[task_id])
            try:
                episode_info = await asyncio.to_thread(resolve_podcast_episode, url)
                resolved_url = episode_info.audio_url
            except Exception as exc:
                parsed_path = (urlparse(url).path or "").lower()
                suffix = Path(parsed_path).suffix
                is_audio_or_feed = (
                    suffix in AUDIO_EXTENSIONS
                    or suffix in {".rss", ".xml"}
                    or "rss" in parsed_path
                    or "feed" in parsed_path
                )
                if is_audio_or_feed:
                    raise Exception(f"播客链接解析失败: {exc}") from exc
                logger.warning(f"播客链接解析失败，尝试使用原始链接继续: {exc}")

        # 下载并转换媒体音频
        audio_path, video_title, media_info = await video_processor.download_and_convert(resolved_url, TEMP_DIR)
        media_title = episode_info.title if episode_info and episode_info.title else video_title
        if not media_title:
            media_title = "untitled"
        
        # 下载完成，更新状态
        meta_payload = {
            "content_type": media_source.content_type,
            "provider": media_source.provider,
            "media_display_name": media_source.display_name,
            "webpage_url": media_info.get("webpage_url") or (episode_info.episode_url if episode_info else url) or url,
            "thumbnail": media_info.get("thumbnail"),
            "uploader": media_info.get("uploader"),
            "source_title": media_info.get("fulltitle") or media_title,
        }
        if episode_info:
            meta_payload.update({
                "episode_url": episode_info.episode_url,
                "feed_url": episode_info.feed_url,
                "audio_url": episode_info.audio_url,
                "audio_mime_type": episode_info.mime_type,
            })

        tasks[task_id].update({
            "progress": 35,
            "message": "音频准备完成，进入转录...",
            "media_metadata": meta_payload
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])
        
        # 更新状态：转录中
        tasks[task_id].update({
            "progress": 40,
            "message": "正在转录音频..."
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])
        
        # 转录音频
        raw_script = await transcriber.transcribe(audio_path)

        short_id = task_id.replace("-", "")[:6]
        safe_title = _sanitize_title_for_filename(media_title)

        # 将Whisper原始转录保存为Markdown文件，供下载/归档
        try:
            raw_md_filename = f"raw_{safe_title}_{short_id}.md"
            raw_md_path = TEMP_DIR / raw_md_filename
            with open(raw_md_path, "w", encoding="utf-8") as f:
                content_raw = (raw_script or "") + f"\n\nsource: {url}\n"
                f.write(content_raw)

            # 记录原始转录文件路径（仅保存文件名，实际路径位于TEMP_DIR）
            tasks[task_id].update({
                "raw_script_file": raw_md_filename
            })
            _persist_task(task_id)
            await broadcast_task_update(task_id, tasks[task_id])
        except Exception as e:
            logger.error(f"保存原始转录Markdown失败: {e}")
        
        # 更新状态：优化转录文本
        tasks[task_id].update({
            "progress": 55,
            "message": "正在优化转录文本..."
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])
        
        # 优化转录文本：修正错别字，按含义分段
        script = await summarizer.optimize_transcript(raw_script)
        
        # 为转录文本添加标题，并在结尾添加来源链接
        script_with_title = f"# {media_title}\n\n{script}\n\nsource: {url}\n"
        
        # 检查是否需要翻译
        detected_language = transcriber.get_detected_language(raw_script)
        logger.info(f"检测到的语言: {detected_language}, 摘要语言: {summary_language}")
        
        translation_content = None
        translation_filename = None
        translation_path = None
        
        if detected_language and translator.should_translate(detected_language, summary_language):
            logger.info(f"需要翻译: {detected_language} -> {summary_language}")
            # 更新状态：生成翻译
            tasks[task_id].update({
                "progress": 70,
                "message": "正在生成翻译..."
            })
            _persist_task(task_id)
            await broadcast_task_update(task_id, tasks[task_id])
            
            # 翻译转录文本
            translation_content = await translator.translate_text(script, summary_language, detected_language)
            translation_with_title = f"# {media_title}\n\n{translation_content}\n\nsource: {url}\n"
            
            # 保存翻译到文件
            translation_filename = f"translation_{safe_title}_{short_id}.md"
            translation_path = TEMP_DIR / translation_filename
            async with aiofiles.open(translation_path, "w", encoding="utf-8") as f:
                await f.write(translation_with_title)
        else:
            logger.info(f"不需要翻译: detected_language={detected_language}, summary_language={summary_language}, should_translate={translator.should_translate(detected_language, summary_language) if detected_language else 'N/A'}")
        
        # 更新状态：生成摘要
        tasks[task_id].update({
            "progress": 80,
            "message": "正在生成摘要..."
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])
        
        # 生成摘要
        summary = await summarizer.summarize(script, summary_language, media_title)
        summary_with_source = summary + f"\n\nsource: {url}\n"
        
        # 保存优化后的转录文本到文件
        script_filename = f"transcript_{task_id}.md"
        script_path = TEMP_DIR / script_filename
        async with aiofiles.open(script_path, "w", encoding="utf-8") as f:
            await f.write(script_with_title)
        
        # 重命名为新规则：transcript_标题_短ID.md
        new_script_filename = f"transcript_{safe_title}_{short_id}.md"
        new_script_path = TEMP_DIR / new_script_filename
        try:
            if script_path.exists():
                script_path.rename(new_script_path)
                script_path = new_script_path
        except Exception as _:
            # 如重命名失败，继续使用原路径
            pass

        # 保存摘要到文件（summary_标题_短ID.md）
        summary_filename = f"summary_{safe_title}_{short_id}.md"
        summary_path = TEMP_DIR / summary_filename
        async with aiofiles.open(summary_path, "w", encoding="utf-8") as f:
            await f.write(summary_with_source)
        
        # 更新状态：完成
        task_result = {
            "status": "completed",
            "progress": 100,
            "message": "处理完成！",
            "video_title": media_title,
            "script": script_with_title,
            "summary": summary_with_source,
            "script_path": str(script_path),
            "summary_path": str(summary_path),
            "short_id": short_id,
            "safe_title": safe_title,
            "detected_language": detected_language,
            "summary_language": summary_language,
            "finished_at": _current_timestamp(),
            "has_translation": bool(translation_path),
            "script_filename": script_path.name,
            "summary_filename": summary_filename
        }
        
        # 如果有翻译，添加翻译信息
        if translation_content and translation_path:
            task_result.update({
                "translation": translation_with_title,
                "translation_path": str(translation_path),
                "translation_filename": translation_filename,
                "has_translation": True
            })
        
        tasks[task_id].update(task_result)
        _persist_task(task_id)
        logger.info(f"任务完成，准备广播最终状态: {task_id}")
        await broadcast_task_update(task_id, tasks[task_id])
        logger.info(f"最终状态已广播: {task_id}")
        
        # 从处理列表中移除URL
        processing_urls.discard(url)
        
        # 从活跃任务列表中移除
        if task_id in active_tasks:
            del active_tasks[task_id]
        
        # 不要立即删除临时文件！保留给用户下载
        # 文件会在一定时间后自动清理或用户手动清理
            
    except Exception as e:
        logger.error(f"任务 {task_id} 处理失败: {str(e)}")
        # 从处理列表中移除URL
        processing_urls.discard(url)
        
        # 从活跃任务列表中移除
        if task_id in active_tasks:
            del active_tasks[task_id]
            
        tasks[task_id].update({
            "status": "error",
            "error": str(e),
            "message": f"处理失败: {str(e)}"
        })
        _persist_task(task_id)
        await broadcast_task_update(task_id, tasks[task_id])

@app.get("/api/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return tasks[task_id]

@app.get("/api/history")
async def list_history(
    page: int = Query(1, ge=1, description="页码（从1开始）"),
    limit: int = Query(20, ge=1, description="每页条目数（最大100）")
):
    """
    获取已完成任务的历史列表。

    参数:
        page (int): 页码，从1开始。
        limit (int): 每页条目数，最大100。
    返回:
        dict: 包含分页信息与历史列表的字典。
    异常:
        HTTPException: 当limit超过100或参数异常时抛出。
    """
    if limit > 100:
        raise HTTPException(status_code=400, detail="limit 最大允许值为 100")

    history_candidates: List = []
    for tid, task_data in tasks.items():
        if task_data.get("status") == "completed":
            completed_task = _ensure_task_metadata(tid)
            history_candidates.append((tid, completed_task))

    history_candidates.sort(
        key=lambda item: item[1].get("finished_at") or item[1].get("created_at") or "",
        reverse=True
    )

    total = len(history_candidates)
    start_index = (page - 1) * limit
    end_index = start_index + limit
    sliced = history_candidates[start_index:end_index]

    items = []
    for tid, task_data in sliced:
        items.append({
            "task_id": tid,
            "url": task_data.get("url"),
            "video_title": task_data.get("video_title"),
            "created_at": task_data.get("created_at"),
            "finished_at": task_data.get("finished_at"),
            "detected_language": task_data.get("detected_language"),
            "summary_language": task_data.get("summary_language"),
            "has_translation": task_data.get("has_translation", False)
        })

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": items
    }

@app.get("/api/history/{task_id}")
async def get_history_detail(task_id: str):
    """
    获取指定任务的完整历史详情。

    参数:
        task_id (str): 任务ID。
    返回:
        dict: 包含脚本、摘要、翻译及下载信息的字典。
    异常:
        HTTPException: 当任务不存在或未完成时抛出404。
    """
    if task_id not in tasks or tasks[task_id].get("status") != "completed":
        raise HTTPException(status_code=404, detail="历史记录不存在或任务未完成")

    task_data = _ensure_task_metadata(task_id)

    return {
        "task_id": task_id,
        "url": task_data.get("url"),
        "video_title": task_data.get("video_title"),
        "created_at": task_data.get("created_at"),
        "finished_at": task_data.get("finished_at"),
        "script": task_data.get("script"),
        "summary": task_data.get("summary"),
        "translation": task_data.get("translation"),
        "detected_language": task_data.get("detected_language"),
        "summary_language": task_data.get("summary_language"),
        "raw_script_file": task_data.get("raw_script_file"),
        "script_filename": task_data.get("script_filename"),
        "summary_filename": task_data.get("summary_filename"),
        "translation_filename": task_data.get("translation_filename"),
        "has_translation": task_data.get("has_translation", False)
    }

@app.delete("/api/history/{task_id}")
async def delete_history_record(task_id: str):
    """
    删除指定历史记录以及关联的Markdown文件。

    参数:
        task_id (str): 历史记录对应的任务ID。
    返回:
        dict: 删除结果信息。
    异常:
        HTTPException: 当历史记录不存在或文件名非法时抛出。
    """
    if task_id not in tasks or tasks[task_id].get("status") != "completed":
        raise HTTPException(status_code=404, detail="历史记录不存在或任务未完成")

    task_data = tasks[task_id]
    filenames = set()

    for filename_key in [
        "script_filename",
        "summary_filename",
        "translation_filename",
        "raw_script_file"
    ]:
        filename = task_data.get(filename_key)
        if filename:
            _validate_history_filename(filename)
            filenames.add(filename)

    for path_key in ["script_path", "summary_path", "translation_path"]:
        candidate_path = task_data.get(path_key)
        if candidate_path:
            try:
                candidate_name = Path(candidate_path).name
                _validate_history_filename(candidate_name)
                filenames.add(candidate_name)
            except Exception:
                logger.warning(f"无法解析待删除文件路径: {candidate_path}")

    for filename in filenames:
        file_path = TEMP_DIR / filename
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as exc:
            logger.warning(f"删除历史文件失败 {file_path}: {exc}")

    del tasks[task_id]
    save_tasks(tasks)
    return {"message": "历史记录已删除"}

@app.get("/api/task-stream/{task_id}")
async def task_stream(task_id: str):
    """
    SSE实时任务状态流
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    async def event_generator():
        # 创建任务专用的队列
        queue = asyncio.Queue()
        
        # 将队列添加到连接列表
        if task_id not in sse_connections:
            sse_connections[task_id] = []
        sse_connections[task_id].append(queue)
        
        try:
            # 立即发送当前状态
            current_task = tasks.get(task_id, {})
            yield f"data: {json.dumps(current_task, ensure_ascii=False)}\n\n"
            
            # 持续监听状态更新
            while True:
                try:
                    # 等待状态更新，超时时间30秒发送心跳
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {data}\n\n"
                    
                    # 如果任务完成或失败，结束流
                    task_data = json.loads(data)
                    if task_data.get("status") in ["completed", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f"data: {json.dumps({'type': 'heartbeat'}, ensure_ascii=False)}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"SSE连接被取消: {task_id}")
        except Exception as e:
            logger.error(f"SSE流异常: {e}")
        finally:
            # 清理连接
            if task_id in sse_connections and queue in sse_connections[task_id]:
                sse_connections[task_id].remove(queue)
                if not sse_connections[task_id]:
                    del sse_connections[task_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """
    直接从temp目录下载文件（简化方案）
    """
    try:
        # 检查文件扩展名安全性
        if not filename.endswith('.md'):
            raise HTTPException(status_code=400, detail="仅支持下载.md文件")
        
        # 检查文件名格式（防止路径遍历攻击）
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="文件名格式无效")
            
        file_path = TEMP_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
            
        return FileResponse(
            file_path,
            filename=filename,
            media_type="text/markdown"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """
    取消并删除任务
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 如果任务还在运行，先取消它
    if task_id in active_tasks:
        task = active_tasks[task_id]
        if not task.done():
            task.cancel()
            logger.info(f"任务 {task_id} 已被取消")
        del active_tasks[task_id]
    
    # 从处理URL列表中移除
    task_url = tasks[task_id].get("url")
    if task_url:
        processing_urls.discard(task_url)
    
    # 删除任务记录
    del tasks[task_id]
    save_tasks(tasks)
    return {"message": "任务已取消并删除"}

@app.get("/api/tasks/active")
async def get_active_tasks():
    """
    获取当前活跃任务列表（用于调试）
    """
    active_count = len(active_tasks)
    processing_count = len(processing_urls)
    return {
        "active_tasks": active_count,
        "processing_urls": processing_count,
        "task_ids": list(active_tasks.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
