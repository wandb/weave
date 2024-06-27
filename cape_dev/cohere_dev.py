from dataclasses import dataclass
import cohere
import os

import weave
import simple_parsing

@dataclass
class Args:
	stream: bool = False
	model: str = "command"

args = simple_parsing.parse(Args)


co = cohere.Client(os.environ["COHERE_API_KEY"])

print("imported cohere")

weave.init("cohere_dev")

if args.stream:
	print("STREAMED")
	response = co.chat_stream(
		chat_history=[
			{"role": "USER", "message": "Who discovered gravity?"},
			{
				"role": "CHATBOT",
				"message": "The man who is widely credited with discovering gravity is Sir Isaac Newton",
			},
		],
		message="What year was he born?",
		# perform web search before answering the question. You can also use your own custom connector.
		connectors=[{"id": "web-search"}],
	)

	for event in response:
		print(event)
		print(event.event_type)
		if event.event_type == "text-generation":
			print(event.text, end='')

else:
	print("NON streamed")
	# response = co.chat(
	# 	chat_history=[
	# 		{"role": "USER", "message": "Who discovered gravity?"},
	# 		{
	# 			"role": "CHATBOT",
	# 			"message": "The man who is widely credited with discovering gravity is Sir Isaac Newton",
	# 		},
	# 	],
	# 	message="What year was he born?",
	# 	# perform web search before answering the question. You can also use your own custom connector.
	# 	connectors=[{"id": "web-search"}],
	# )
	# print(response)

	print("simple")
	response = co.chat(
		model=args.model, 
		message="Hi, how are you?",
	)
	print(response)
