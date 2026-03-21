import json
import os

from dotenv import load_dotenv
from openai import OpenAI


class LLMClient(object):

    def __init__(self):

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("MODEL_ID")
        base_url = os.getenv("BASE_URL")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        # models = self.client.models.list()
        # model_name = models.data[0].id

        print(f"save_model_name : {model_name}")
        self.model_name = model_name

    def inference(self, messages, system_prompt, tool_schema):
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                max_tokens=8096,
                tools=tool_schema,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                tool_choice="auto"
            )
            error_msg = None
        except Exception as exc:
            error_msg = exc
            response = None

        parsed_response = {}
        if response:
            content = response.choices[0].message.content
            stop_reason = response.choices[0].finish_reason
            parsed_response["status"] = "succeed"
            parsed_response["content"] = content
            parsed_response["stop_reason"] = stop_reason
            if stop_reason == "tool_calls":
                tool_list = []
                tool_calls = response.choices[0].message.tool_calls
                for tool_call in tool_calls:
                    tool_list.append({
                        "function_name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                        "tool_call_id": tool_call.id,
                    })
                parsed_response["tools"] = tool_list
        else:
            parsed_response["status"] = "failed"
            parsed_response["message"] = error_msg

        return parsed_response
