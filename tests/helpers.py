import json


class FakeOpenAIMessage:
    def __init__(self, content):
        self.content = content


class FakeOpenAIChoice:
    def __init__(self, content):
        self.message = FakeOpenAIMessage(content)


class FakeOpenAIResponse:
    def __init__(self, content):
        self.choices = [FakeOpenAIChoice(content)]


class FakeOpenAIClient:
    def __init__(self, content):
        self.chat = type(
            "ChatNamespace",
            (),
            {
                "completions": type(
                    "CompletionsNamespace",
                    (),
                    {"create": lambda *args, **kwargs: FakeOpenAIResponse(content)},
                )()
            },
        )()


def make_openai_json_response(payload: dict) -> FakeOpenAIResponse:
    return FakeOpenAIResponse(json.dumps(payload))
