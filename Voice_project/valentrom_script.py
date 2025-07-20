import tkinter as tk

def create_gui():
    window = tk.Tk()
    window.title("Valentine's Day Card Generator")

    name_label = tk.Label(window, text="Enter your name: ")
    name_label.pack()
    name_entry = tk.Entry(window)
    name_entry.pack()

    recipient_label = tk.Label(window, text="Enter the recipient's name: ")
    recipient_label.pack()
    recipient_entry = tk.Entry(window)
    recipient_entry.pack()

    message_label = tk.Label(window, text="Enter your message: ")
    message_label.pack()
    message_entry = tk.Text(window)
    message_entry.pack()

    def generate_card():
        name = name_entry.get()
        recipient = recipient_entry.get()
        message = message_entry.get("1.0", "end")

        card_text = f"""
                   Valentine's Day Card
                    To {recipient},
                    Happy Valentine's Day!
                    {message}
                                -{name}
                      """
        tk.Label(window, text=card_text, font=("Arial", 16), wraplength=350, justify="center").pack()

    generate_button = tk.Button(window, text="Generate Card", command=generate_card)
    generate_button.pack()

    window.mainloop()

create_gui()