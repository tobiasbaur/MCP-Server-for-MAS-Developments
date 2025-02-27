import argparse
import os
import shutil
from random import choices

import gradio as gr
from openai import OpenAI

parser = argparse.ArgumentParser(description="Provide an API key to connect to OpenAI-compatible API.")
parser.add_argument("--api_key", required=True, help="API key for login")
parser.add_argument("--base_url", required=True, help="The base url of the VLLM server")
args = parser.parse_args()


def predict(message, history):
    history_openai_format = []
    for human, assistant in history:
        history_openai_format.append({"role": "user", "content": human })
        history_openai_format.append({"role": "assistant", "content":assistant})
    history_openai_format.append({"role": "user", "content": message})

    client = OpenAI(
        base_url=args.base_url,
        api_key=args.api_key,
    )

    completion = client.chat.completions.create(
        model="/models/mistral-nemo-12b",
        messages= history_openai_format,
        temperature=1.0,
        stream=True
    )

    partial_message = ""
    for chunk in completion:
        if len(chunk.choices[0].delta.content) != 0:
            partial_message = partial_message + chunk.choices[0].delta.content
            yield partial_message







with gr.Blocks(theme="ocean",  css="footer {visibility: hidden}") as demo:
    with gr.Tab("Chat"):
        gr.ChatInterface(predict,
                         chatbot=gr.Chatbot(height=500),
                         textbox=gr.Textbox(placeholder="Ask me a question", container=False, scale=7),
                         title="PrivateGPT",
                         description="Demo for the PrivateGPT API",
                         theme="ocean",
                         examples=["Hello", "Write a Python function that counts all numbers from 1 to 10",
                                   "Are tomatoes vegetables?"],
                         cache_examples=False,
                         )
    with gr.Tab("Sources"):
        def upload_file(file):
            UPLOAD_FOLDER = "./data"
            if not os.path.exists(UPLOAD_FOLDER):
                os.mkdir(UPLOAD_FOLDER)
            shutil.copy(file, UPLOAD_FOLDER)
            gr.Info("File Uploaded!!!")


        upload_button = gr.UploadButton("Click to Upload a File")
        upload_button.upload(upload_file, upload_button)

    with gr.Tab("Users"):
        # Define a function that will process the selected elements

        # Create a list of elements for selection
        elements = ["User1", "User2", "User3", "User4", "User5"]


        def rs_change(rs):
            return gr.update(choices=elements, value=None)

        def process_selection(selected_elements):
            print(selected_elements)
            return f"You selected: {', '.join(selected_elements)}"

        checkboxes = gr.CheckboxGroup(choices=elements, label="Select Users to delete.", interactive=True)

        # Create a Gradio interface
        iface = gr.Interface(
            fn=process_selection,
            inputs=checkboxes,
            outputs="text",
            title="User Management",
            theme="ocean",
            description="Select users to delete.",
            live = True,
            clear_btn=None,
            flagging_mode="never"

        )



        def submit_selection(selected_elements):
            for element in selected_elements:
                elements.remove(element)

            gr.Info("Users deleted")
            gr.update(value="The UI has been refreshed!")
            #checkboxes.change(fn=rs_change, inputs=[rs], outputs=[rs_hw])


        upload_button = gr.Button("Submit")
        upload_button.click(fn=submit_selection, inputs=checkboxes)


demo.launch()

