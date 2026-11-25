# 🗳️ Dynamic Team Poll App (Self-Hosted for Microsoft Teams)

A dynamic, multi-poll web application allowing you to create **any poll you want** on the fly with custom questions and custom options. Every poll gets its own unique **Vote Link** and **Live Results Link**.

Completely independent and isolated in `/home/rajesh/team-poll-app` (no dependency on ERP or Telegram bot).

---

## 🔗 Main Dashboard (Create & Manage Polls)

- **🌐 Public URL (Accessible Anywhere):**  
  `https://enormous-novel-bag-pasta.trycloudflare.com`

- **🏠 Local Network URL:**  
  `http://192.168.13.144:8095`

---

## ✨ Features

1. **Create Any Poll on Demand:**
   - Enter your question (e.g. Lunch, Standup time, Outing venue, Quick decision).
   - Add as many custom options as you want using `+ Add Option`.
   - Quick templates provided (Lunch, Standup Timing, Outing, Simple Yes/No).
2. **Instant Unique Links Generated:**
   - **Vote Link:** e.g. `https://<domain>/p/<poll-id>` (Share this in Microsoft Teams!)
   - **Results Link:** e.g. `https://<domain>/r/<poll-id>` (Live auto-refreshing results dashboard!)
3. **Attendee & Preference Tracking:**
   - Records each voter's name, choice, and optional note (e.g., *"Pure Veg"*, *"Joining at 1:30 PM"*).
   - Upsert capability: voters can change their answer anytime using their name.
4. **1-Click Microsoft Teams Summary:**
   - Results dashboard has a **📋 Copy for Teams** button that copies a nicely formatted summary ready to paste straight into Microsoft Teams.
5. **Manage Past Polls:**
   - View response counts, open links, or delete old polls from the dashboard.

---

## 🛠️ Commands

```bash
# Check status and see current links
/home/rajesh/team-poll-app/status.sh

# Start or restart
/home/rajesh/team-poll-app/start.sh

# Stop the app
/home/rajesh/team-poll-app/stop.sh
```
