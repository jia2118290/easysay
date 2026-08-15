"""Azure 发音评测 Worker"""
import json

from PySide6.QtCore import QThread, Signal

# UI 语言标签 -> Azure 发音评测 BCP-47 区域码
AZURE_LANG_MAP = {
    "英语 (en)": "en-US",
    "日语 (ja)": "ja-JP",
    "韩语 (ko)": "ko-KR",
    "法语 (fr)": "fr-FR",
    "意大利语 (it)": "it-IT",
    "西班牙语 (es)": "es-ES",
    "中文 (zh)": "zh-CN",
}

# 未显式指定时的默认评测语言
DEFAULT_AZURE_LANG = "en-US"


class PronunciationWorker(QThread):
    finished_signal = Signal(bool, dict)  # (success, scores_or_error_dict)

    def __init__(self, wav_path: str, reference_text: str,
                 speech_key: str, speech_region: str, language: str = ""):
        super().__init__()
        self.wav_path = wav_path
        self.reference_text = reference_text
        self.speech_key = speech_key
        self.speech_region = speech_region
        self.language = language

    def run(self):
        # 参考文本为空 → 前端应该在调用前校验，这里也兜个底
        if not self.reference_text or not self.reference_text.strip():
            self.finished_signal.emit(
                False,
                {"error": "参考文本为空，无法进行发音评测", "category": "empty_reference"},
            )
            return

        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            self.finished_signal.emit(
                False,
                {"error": "未安装 Azure 语音 SDK，请运行: pip install azure-cognitiveservices-speech",
                 "category": "sdk_missing"},
            )
            return

        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, region=self.speech_region,
            )
            speech_config.speech_recognition_language = AZURE_LANG_MAP.get(
                self.language, DEFAULT_AZURE_LANG
            )
            audio_config = speechsdk.audio.AudioConfig(filename=self.wav_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, audio_config=audio_config,
            )

            pron_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=self.reference_text,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            )
            pron_config.apply_to(recognizer)

            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                scores = self._extract_scores(result)
                self.finished_signal.emit(True, scores)
            elif result.reason == speechsdk.ResultReason.NoMatch:
                self.finished_signal.emit(
                    False,
                    {"error": "未检测到有效语音，请确保麦克风已开启并重试",
                     "category": "no_match"},
                )
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self._handle_cancellation(cancellation)
            else:
                self.finished_signal.emit(
                    False, {"error": f"语音识别未返回结果：{result.reason}",
                            "category": "unknown_result"},
                )
        except Exception as e:  # noqa: BLE001
            self._classify_exception(e)

    def _handle_cancellation(self, cancellation):
        reason_str = str(cancellation.reason)
        error_code = str(cancellation.error_code) if cancellation.error_code else ""
        details = cancellation.error_details or ""
        lower_details = details.lower()

        if "unauthorized" in lower_details or "401" in lower_details or \
           "authentication" in error_code.lower():
            self.finished_signal.emit(
                False,
                {"error": "密钥无效 (401)：请检查 Azure Speech API Key 是否正确",
                 "category": "invalid_key"},
            )
        elif "connection" in error_code.lower() or "timeout" in lower_details or \
             "dns" in lower_details or "name resolution" in lower_details:
            self.finished_signal.emit(
                False,
                {"error": "网络连接失败：请检查网络或 Region 地址是否正确",
                 "category": "network"},
            )
        elif "region" in lower_details.lower() and ("not found" in lower_details or "invalid" in lower_details):
            self.finished_signal.emit(
                False,
                {"error": f"区域配置错误：Region 无效或服务不可用\n{details}",
                 "category": "invalid_region"},
            )
        else:
            self.finished_signal.emit(
                False,
                {"error": f"语音识别被取消：{reason_str}\n{details}",
                 "category": "cancelled"},
            )

    def _classify_exception(self, e: Exception):
        msg = str(e)

        # 网络/DNS 错误（含区域填错导致的连不上）
        if any(kw in msg for kw in (
            "getaddrinfo", "NameResolution", "name resolution",
            "ConnectionRefusedError", "ConnectionError", "Timeout",
            "timed out", "Temporary failure", "Network is unreachable",
        )):
            if "speech" in msg.lower() or "cognitiveservices" in msg.lower():
                self.finished_signal.emit(
                    False,
                    {"error": f"网络连接失败：可能是 Region 地址填错或无法访问 ({msg})",
                     "category": "network_or_region"},
                )
            else:
                self.finished_signal.emit(
                    False,
                    {"error": f"网络连接失败：请检查网络 ({msg})",
                     "category": "network"},
                )
        elif any(kw in msg for kw in ("401", "unauthorized", "Unauthorized")):
            self.finished_signal.emit(
                False,
                {"error": f"密钥无效 (401)：请检查 Azure Speech API Key 是否正确",
                 "category": "invalid_key"},
            )
        else:
            self.finished_signal.emit(
                False,
                {"error": f"评分服务异常：{msg}", "category": "unknown"},
            )

    @staticmethod
    def _extract_scores(result) -> dict:
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            return {"error": "SDK not installed"}

        json_str = result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        if not json_str:
            return {"error": "未收到发音评测结果"}

        data = json.loads(json_str)
        nbest = data.get("NBest", [{}])
        best = nbest[0]
        assessment = best.get("PronunciationAssessment", {})

        words = []
        for w in best.get("Words", []):
            w_assessment = w.get("PronunciationAssessment", {})
            words.append({
                "word": w.get("Word", ""),
                "accuracy": w_assessment.get("AccuracyScore", 0),
                "error_type": w_assessment.get("ErrorType", ""),
            })

        return {
            "overall": assessment.get("PronScore", 0),
            "accuracy": assessment.get("AccuracyScore", 0),
            "fluency": assessment.get("FluencyScore", 0),
            "completeness": assessment.get("CompletenessScore", 0),
            "prosody": assessment.get("ProsodyScore", 0),
            "words": words,
        }
