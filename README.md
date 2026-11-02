# 🚀 Instapaper Multi-Account Link Automation

Ek powerful aur fully automated system jo Instapaper me kitni bhi links (10, 50, 150 ya 1000+) save karta hai. 
Ye **Sequential Account Pipeline** follow karta hai: Pehle **Account 1** me saari links save hoti hain, fir **Account 2** me, fir **Account 3** me... aur saaton accounts par 100% complete hoti hain.

---

## 📁 File Structure

- **`run.bat`** : 1-Click Windows Runner (Double click to start).
- **`accounts.json`** : Yahan tumhare accounts ki Cookies / Session IDs save hoti hain (*.gitignore me protected hai*).
- **`accounts.example.json`** : Dummy template configuration file.
- **`links.txt`** : Yahan apni links paste karni hain (har line par ek URL).
- **`main.py`** : Core sequential engine jo dynamic CSRF `form_key` extract karke verified additions karta hai.
- **`state.json`** : Auto-generated ledger (har account ka alag record rakhta hai taaki duplicate work na ho).

---

## 🛠️ Setup Instructions (Step-by-Step)

### Step 1: `accounts.json` Setup Karo
`accounts.example.json` ko copy karke `accounts.json` banao aur apne har account ki cookie string paste karo:
```json
[
  {
    "id": 1,
    "name": "Account 1",
    "cookie": "pfus=xxxx...; _xsrf=xxxx...; form_key=xxxx...",
    "enabled": true
  }
]
```

### Step 2: `links.txt` Me Links Paste Karo
Jitni marzi links ho (10 ho ya 1000), `links.txt` me paste kar do:
```text
https://in.pinterest.com/pin/1091489659727124935/
https://in.pinterest.com/pin/1091489659727125954/
https://in.pinterest.com/pin/1091489659727127145/
```

### Step 3: `run.bat` Par Double Click Karo!
- Automatically Python environment setup karega.
- Pehle Account 1 ke saare links complete karega.
- Fir Account 2, fir Account 3... aise saaton accounts par 100% execute karega!

---

## 🛡️ Key Features
- **Strict Verification:** Instapaper ke real API response (`bookmark.id`) ko verify karta hai.
- **Per-Account State:** Agar beech me internet band ho jaye, dubara chalane par pehle se completed links skip ho jayenge aur pending links se resume hoga.
- **Anti-Rate Limit Delays:** Har link ke beech randomized human delays (2.5s - 4.5s) lagata hai taaki account bilkul safe rahe.
