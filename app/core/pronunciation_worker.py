"""Azure 发音评测 Worker"""
import json

from PySide6.QtCore import QThread, Signal


class PronunciationWorker(QThread):
    finished_signal = Signal(bool, dict)  # (success, scores_or_error)

    def __init__(self, wav_path: str, reference_text: str,
                 speech_key: str, speech_region: str):
        super().__init__()
        self.wav_path = wav_path
        self.reference_text = reference_text
        self.speech_key = speech_key
        self.speech_region = speech_region

    def run(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            self.finished_signal.emit(
                False,
                {"error": "未安装 Azure 语音 SDK，请运行: pip install azure-cognitiveservices-speech"},
            )
            return

        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, region=self.speech_region,
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
                    {"error": "未检测到有效语音，请确保麦克风已开启并重试"},
                )
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.finished_signal.emit(
                    False,
                    {"error": f"语音识别被取消：{cancellation.reason}\n{cancellation.error_details or ''}"},
                )
            else:
                self.finished_signal.emit(
                    False, {"error": f"语音识别未返回结果：{result.reason}"},
                )
        except Exception as e:  # noqa: BLE001
            self.finished_signal.emit(False, {"error": f"评分服务异常：{e}"})

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
        assessment = nbest[0].get("PronunciationAssessment", {})

        return {
            "overall": assessment.get("PronScore", 0),
            "accuracy": assessment.get("AccuracyScore", 0),
            "fluency": assessment.get("FluencyScore", 0),
            "completeness": assessment.get("CompletenessScore", 0),
            "prosody": assessment.get("ProsodyScore", 0),
        }
