import tkinter as tk
from tkinter import messagebox, ttk
import csv
import datetime

departments = {
    "Garbage Collection": "Sanitation Department",
    "Road Damage": "Public Works Department",
    "Streetlights": "Electrical Department",
    "Water Supply": "Water Department",
    "Drainage": "Drainage Department"
}

def save_complaint(name, address, contact, category, desc):
    dept = departments.get(category, "General Department")
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("complaints.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time_stamp, name, address, contact, category, dept, desc])
    return dept

def submit():
    name = entry_name.get()
    address = entry_address.get()
    contact = entry_contact.get()
    category = combo_category.get()
    desc = text_desc.get("1.0", tk.END).strip()
    if not (name and address and contact and category and desc):
        messagebox.showerror("Error", "All fields are required!")
        return
    dept = save_complaint(name, address, contact, category, desc)
    messagebox.showinfo("Submitted", f"Complaint submitted! Routed to: {dept}")
    entry_name.delete(0, tk.END)
    entry_address.delete(0, tk.END)
    entry_contact.delete(0, tk.END)
    combo_category.set("")
    text_desc.delete("1.0", tk.END)

root = tk.Tk()
root.title("Municipal/Smart City Complaint System 🌆")
root.geometry("500x500")

tk.Label(root, text="Municipal Complaint System", font=("Arial", 16, "bold"), fg="blue").pack(pady=10)
frame = tk.Frame(root)
frame.pack(pady=5)

tk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w")
entry_name = tk.Entry(frame, width=40)
entry_name.grid(row=0, column=1)

tk.Label(frame, text="Address:").grid(row=1, column=0, sticky="w")
entry_address = tk.Entry(frame, width=40)
entry_address.grid(row=1, column=1)

tk.Label(frame, text="Contact:").grid(row=2, column=0, sticky="w")
entry_contact = tk.Entry(frame, width=40)
entry_contact.grid(row=2, column=1)

tk.Label(frame, text="Category:").grid(row=3, column=0, sticky="w")
combo_category = ttk.Combobox(frame, values=list(departments.keys()), width=37)
combo_category.grid(row=3, column=1)

tk.Label(frame, text="Description:").grid(row=4, column=0, sticky="nw")
text_desc = tk.Text(frame, width=30, height=5)
text_desc.grid(row=4, column=1, pady=5)

tk.Button(root, text="Submit Complaint", command=submit, bg="green", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
root.mainloop()