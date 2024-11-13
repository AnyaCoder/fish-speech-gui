import re
from typing import Literal

from .schema import ServeMessage, ServeTextPart, ServeVQPart


class ChatState:
    def __init__(self):
        self.conversation: list[ServeMessage] = []
        self.added_systext = False
        self.added_sysaudio = False
        self.readable_history = []
        self.last_processed_index = -1

    def get_history(self, mode: Literal["all", "new"] = "all") -> list[dict[str, str]]:
        new_results = []
        for msg in self.conversation[self.last_processed_index + 1 :]:
            new_results.append({"role": msg.role, "content": self.repr_message(msg)})

        # Process assistant messages to extract questions and update user messages
        for i, msg in enumerate(new_results):
            if msg["role"] == "assistant":
                match = re.search(r"Question: (.*?)\n\nResponse:", msg["content"])
                if match and i > 0 and new_results[i - 1]["role"] == "user":
                    # Update previous user message with extracted question
                    new_results[i - 1]["content"] += "\n" + match.group(1)
                    # Remove the Question/Answer format from assistant message
                    msg["content"] = msg["content"].split("\n\nResponse: ", 1)[1]

        self.readable_history.extend(new_results)
        self.last_processed_index = len(self.conversation) - 1
        return self.readable_history if mode == "all" else new_results

    def repr_message(self, msg: ServeMessage):
        response = ""
        for part in msg.parts:
            if isinstance(part, ServeTextPart):
                response += part.text
            elif isinstance(part, ServeVQPart):
                response += f"<audio {len(part.codes[0]) / 21:.2f}s>"
        return response

    def append_to_chat_ctx(
        self, part: ServeTextPart | ServeVQPart, role: str = "assistant"
    ) -> None:
        if not self.conversation or self.conversation[-1].role != role:
            self.conversation.append(ServeMessage(role=role, parts=[part]))
        else:
            self.conversation[-1].parts.append(part)

    def clear(self):
        self.__init__()  # Re-initialize
