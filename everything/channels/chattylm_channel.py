import os
import textwrap
from everything.things.channel import ACCESS_PERMITTED, Channel, access_policy
import everything.things.util as util
from transformers import AutoTokenizer, AutoModelForCausalLM


os.environ['TOKENIZERS_PARALLELISM'] = 'true'


# This class is an example of how you can create a channel that constructs
# a prompt using the message log and sends it to a backend language model.


class ChattyLMChannel(Channel):
  """
  Encapsulates a chatting AI backed by a language model
  Currently uses transformers library as a backend provider
  """

  def __init__(self, operator, **kwargs):
    super().__init__(operator, **kwargs)
    # initialize transformers model
    self.tokenizer = AutoTokenizer.from_pretrained(kwargs['model'])
    self.tokenizer.pad_token = self.tokenizer.eos_token
    self.model = AutoModelForCausalLM.from_pretrained(kwargs['model'])

  def _message_log_to_list(self, indent=None):
    """Convert an array of message_log entries to a prompt ready list"""
    promptable_list = ""
    for message in self._message_log:
      promptable_list += self._message_line(message, indent)
    return promptable_list

  def _message_line(self, message, indent=None):
    """
    Returns a single line appropriate for a prompt that represents a previous
    message
    """
    pre_prompt = self._pre_prompt(message['from'].split('.')[0])
    # Here we format what a previous message looks like in the prompt
    # For "say" actions, we just present the content as a line of text
    if message['action'] == 'say':
      return f"\n{pre_prompt} {message['args']['content']}"
    # For all other actions, we present the full JSON message. This
    # is more useful for Agents, but is here just as a demonstration.
    # A chatting AI would probably only deal with "say" actions.
    return f"\n{pre_prompt} {message}"

  def __prompt_head(self):
    """
    Returns the head portion of the prompt containing context/instructions
    """
    return textwrap.dedent(f"""
    Below is a conversation between "ChattyAI", an awesome AI that follows
    instructions and a human who they serve.
    """)

  def _pre_prompt(self, channel_id, timestamp=util.to_timestamp()):
    return f"\n### {channel_id.split('.')[0]}: "

  @access_policy(ACCESS_PERMITTED)
  def _action__say(self, content: str) -> bool:
    """
    Use this action to say something to Chatty
    """
    # Here we demonstrate constructing a full prompt using previous messages for
    # context
    full_prompt = \
      self.__prompt_head() + \
      self._message_log_to_list() + \
      self._pre_prompt(self.id())
    util.debug(f"Sending full_prompt to LM:", full_prompt)
    input_ids = self.tokenizer.encode(full_prompt, return_tensors="pt")
    output = self.model.generate(
      input_ids,
      attention_mask=input_ids.new_ones(input_ids.shape),
      do_sample=True,
      max_new_tokens=50,
    )
    new_tokens = output[0][input_ids.shape[1]:]
    response_text = self.tokenizer.decode(
      new_tokens,
      skip_special_tokens=True,
    )
    response_content = response_text.split('\n###')[0]
    self._send({
      "to": self._current_message['from'],
      "thoughts": "",
      "action": "say",
      "args": {
        "content": response_content,
      }
    })
