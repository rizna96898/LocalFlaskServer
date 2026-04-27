from llama_cpp import Llama

class LocalLlamaService:
    def __init__(self):
        print("Loading model...")
        self.llm = Llama(
            model_path="E:\\LocalFlaskServer\\models\\mythomax\\mythomax-l2-13b.Q5_K_M.gguf",
            n_ctx=4096,
            n_gpu_layers=-1,
        )
        print("Model loaded")

    def send_message(self, prompt, **kwargs):
        return self.llm(prompt, **kwargs)