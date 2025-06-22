import random

class MistralBot:
    def __init__(self):
        self.running = False

    def start(self):

        self._run_loop()

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            print("MistralBot is running...")
