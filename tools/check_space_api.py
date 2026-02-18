
from gradio_client import Client

def check_api(space_id):
    print(f"\n--- Checking API for: {space_id} ---")
    try:
        client = Client(space_id)
        client.view_api()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    candidates = [
        "guoqincode/SadTalker",
        "camenduru/sad-talker",
        "yzt/SadTalker",
        "fudan-generative-ai/hallo" # Might be private/gated
    ]
    for c in candidates:
        check_api(c)
