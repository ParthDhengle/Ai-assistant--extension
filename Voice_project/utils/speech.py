import pyttsx3

def speak(text):
    print("🔊 Speaking:", text)
    engine = pyttsx3.init()
    engine.setProperty('rate', 170)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
