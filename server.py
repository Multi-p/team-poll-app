#!/usr/bin/env python3
"""
Dynamic Team Poll Server
Allows creating unlimited custom polls with dynamic options, questions,
and dedicated vote/results links for each poll.
"""

import os
import sys
import json
import uuid
import re
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Indian Standard Time (UTC + 05:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_now():
    return datetime.now(IST)

def get_now_str():
    return get_now().strftime("%I:%M %p, %d %b")

PORT = 8095
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
DATA_FILE = os.path.join(APP_DIR, "data", "polls.json")

data_lock = threading.Lock()

def is_poll_admin(poll, device_token=None, admin_key=None):
    if not poll:
        return False
    # If explicit admin key matches
    if admin_key and poll.get("admin_key") and poll.get("admin_key") == admin_key:
        return True
    # If device token matches creator
    if device_token and poll.get("creator_token") and poll.get("creator_token") == device_token:
        return True
    # If device token matches any co-admin
    if device_token:
        for adm in poll.get("admins", []):
            if isinstance(adm, dict) and adm.get("device_token") == device_token:
                return True
            elif isinstance(adm, str) and adm == device_token:
                return True
    return False

def is_poll_creator(poll, device_token=None, admin_key=None):
    if not poll:
        return False
    if admin_key and poll.get("admin_key") and poll.get("admin_key") == admin_key:
        return True
    if device_token and poll.get("creator_token") and poll.get("creator_token") == device_token:
        return True
    return False

def get_initial_data():
    sample_id = "team-lunch"
    return {
        "polls": {
            sample_id: {
                "id": sample_id,
                "question": "🍽️ Are you ready for today's team lunch?",
                "description": "Please submit your response so we can finalize head count & reservation!",
                "created_at": get_now().strftime("%Y-%m-%d %H:%M"),
                "options": [
                    {"id": "opt-1", "label": "Yes, I'm coming! 🎉", "color": "#10b981"},
                    {"id": "opt-2", "label": "No, can't make it ❌", "color": "#ef4444"},
                    {"id": "opt-3", "label": "Maybe / Tentative 🤔", "color": "#f59e0b"}
                ],
                "votes": []
            }
        }
    }

def load_data():
    if not os.path.exists(DATA_FILE):
        data = get_initial_data()
        save_data(data)
        return data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "polls" not in data:
                data = {"polls": {}}
            return data
    except Exception as e:
        print(f"Error reading {DATA_FILE}: {e}")
        return {"polls": {}}

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:25].strip('-') or "poll"

class DynamicPollHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filepath, content_type="text/html; charset=utf-8"):
        if not os.path.exists(filepath):
            self.send_error(404, "Page Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 1. Routing for Web Pages
        # Home page = Poll Dashboard & Creator
        if path == "/" or path == "/dashboard":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"))
            return

        # Vote page for a poll (either /p/<id> or /vote?id=<id> or /poll/<id>)
        if path.startswith("/p/") or path == "/vote" or path.startswith("/poll/"):
            self.serve_file(os.path.join(STATIC_DIR, "vote.html"))
            return

        # Results page for a poll (either /r/<id> or /results or /results/<id>)
        if path.startswith("/r/") or path == "/results" or path.startswith("/results/"):
            self.serve_file(os.path.join(STATIC_DIR, "results.html"))
            return

        # 2. REST API Endpoints
        # Health check
        if path == "/api/status":
            self.send_json(200, {"status": "ok", "app": "Dynamic Team Poll App"})
            return

        # List user's polls (only polls the user created, voted in, or is admin of)
        if path == "/api/polls":
            device_token = query.get("device_token", [None])[0] or self.headers.get("X-Device-Token")
            voter_name = query.get("name", [None])[0]
            poll_ids_param = query.get("poll_ids", [None])[0]
            known_poll_ids = set(poll_ids_param.split(",")) if poll_ids_param else set()

            with data_lock:
                data = load_data()
                poll_list = []
                for pid, p in data.get("polls", {}).items():
                    role = None
                    my_choice = None

                    # Check creator
                    if device_token and p.get("creator_token") == device_token:
                        role = "creator"
                    # Check admin
                    elif device_token and any((a.get("device_token") == device_token if isinstance(a, dict) else a == device_token) for a in p.get("admins", [])):
                        role = "admin"

                    # Check vote
                    for v in p.get("votes", []):
                        if (device_token and v.get("device_token") == device_token) or \
                           (voter_name and v.get("voter_name", "").strip().lower() == voter_name.strip().lower()):
                            if not role:
                                role = "voter"
                            my_choice = v.get("option_label")
                            break

                    # Check known poll IDs saved in voter's browser
                    if not role and pid in known_poll_ids:
                        role = "participant"

                    # Only show if user is involved
                    if role:
                        poll_list.append({
                            "id": pid,
                            "question": p.get("question", "Untitled Poll"),
                            "description": p.get("description", ""),
                            "created_at": p.get("created_at", ""),
                            "options_count": len(p.get("options", [])),
                            "total_votes": len(p.get("votes", [])),
                            "role": role,
                            "my_choice": my_choice,
                            "can_delete": role == "creator"
                        })

                # Sort newest first
                poll_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                self.send_json(200, {"polls": poll_list})
            return

        # Get specific poll data: /api/poll/<id> or /api/poll?id=<id>
        if path.startswith("/api/poll/") or path == "/api/poll":
            poll_id = None
            if path.startswith("/api/poll/"):
                poll_id = path[len("/api/poll/"):].strip("/")
            elif "id" in query:
                poll_id = query["id"][0]

            with data_lock:
                data = load_data()
                polls = data.get("polls", {})
                if not poll_id or poll_id not in polls:
                    # If default requested or not found, fallback to first available
                    if not poll_id and polls:
                        poll_id = next(iter(polls))
                    else:
                        self.send_json(404, {"error": f"Poll '{poll_id}' not found"})
                        return

                poll = polls[poll_id]
                my_vote = None
                device_token = query.get("device_token", [None])[0]
                if device_token:
                    for v in poll.get("votes", []):
                        if v.get("device_token") == device_token:
                            my_vote = {
                                "option_id": v.get("option_id"),
                                "option_label": v.get("option_label"),
                                "comment": v.get("comment", ""),
                                "voter_name": v.get("voter_name", "")
                            }
                            break

                self.send_json(200, {
                    "id": poll["id"],
                    "question": poll["question"],
                    "description": poll.get("description", ""),
                    "options": poll["options"],
                    "total_votes": len(poll.get("votes", [])),
                    "created_at": poll.get("created_at", ""),
                    "my_vote": my_vote
                })
            return

        # Get specific poll results: /api/results/<id> or /api/results?id=<id>
        if path.startswith("/api/results/") or path == "/api/results":
            poll_id = None
            if path.startswith("/api/results/"):
                poll_id = path[len("/api/results/"):].strip("/")
            elif "id" in query:
                poll_id = query["id"][0]

            with data_lock:
                data = load_data()
                polls = data.get("polls", {})
                if not poll_id or poll_id not in polls:
                    if not poll_id and polls:
                        poll_id = next(iter(polls))
                    else:
                        self.send_json(404, {"error": f"Poll '{poll_id}' not found"})
                        return

                poll = polls[poll_id]

                # Check admin privileges
                device_token = query.get("device_token", [None])[0] or self.headers.get("X-Device-Token")
                admin_key = query.get("admin_key", [None])[0] or query.get("key", [None])[0] or self.headers.get("X-Admin-Key")

                # Auto-initialize legacy polls
                if "admin_key" not in poll:
                    poll["admin_key"] = "adm_" + uuid.uuid4().hex[:12]
                    save_data(data)
                if not poll.get("creator_token") and device_token:
                    poll["creator_token"] = device_token
                    save_data(data)

                is_admin = is_poll_admin(poll, device_token, admin_key)

                co_admin_names = [
                    (a.get("voter_name") if isinstance(a, dict) else a)
                    for a in poll.get("admins", [])
                ]

                votes = poll.get("votes", [])
                total = len(votes)

                opt_map = {
                    opt["id"]: {
                        "label": opt["label"],
                        "color": opt.get("color", "#3b82f6"),
                        "count": 0,
                        "voters": []
                    } for opt in poll.get("options", [])
                }

                for v in votes:
                    oid = v.get("option_id")
                    if oid in opt_map:
                        opt_map[oid]["count"] += 1
                        opt_map[oid]["voters"].append({
                            "name": v.get("voter_name", "Anonymous"),
                            "comment": v.get("comment", ""),
                            "time": v.get("voted_at", "")
                        })

                breakdown = []
                for opt in poll.get("options", []):
                    oid = opt["id"]
                    item = opt_map.get(oid, {"label": opt["label"], "color": opt.get("color", "#3b82f6"), "count": 0, "voters": []})
                    count = item["count"]
                    pct = round((count / total * 100), 1) if total > 0 else 0
                    breakdown.append({
                        "id": oid,
                        "label": item["label"],
                        "color": item["color"],
                        "count": count,
                        "percentage": pct,
                        "voters": item["voters"]
                    })

                sanitized_recent = [
                    {
                        "voter_name": v.get("voter_name", "Anonymous"),
                        "option_id": v.get("option_id"),
                        "option_label": v.get("option_label"),
                        "comment": v.get("comment", ""),
                        "voted_at": v.get("voted_at", "")
                    }
                    for v in reversed(votes)
                ]

                self.send_json(200, {
                    "id": poll["id"],
                    "question": poll["question"],
                    "description": poll.get("description", ""),
                    "total_votes": total,
                    "breakdown": breakdown,
                    "recent_votes": sanitized_recent,
                    "options": poll.get("options", []),
                    "is_admin": is_admin,
                    "admin_key": poll.get("admin_key") if is_admin else None,
                    "co_admins": co_admin_names,
                    "server_time": get_now().strftime("%Y-%m-%d %H:%M:%S")
                })
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        # 1. Create a brand new dynamic poll
        if path == "/api/poll/create":
            question = (body.get("question") or "").strip()
            description = (body.get("description") or "").strip()
            raw_options = body.get("options", [])

            if not question:
                self.send_json(400, {"error": "Poll question is required"})
                return

            # Clean options
            options = []
            palette = ["#10b981", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
            for idx, opt in enumerate(raw_options):
                lbl = (opt.get("label") if isinstance(opt, dict) else str(opt)).strip()
                if lbl:
                    color = opt.get("color") if isinstance(opt, dict) and opt.get("color") else palette[idx % len(palette)]
                    options.append({
                        "id": f"opt-{idx+1}",
                        "label": lbl,
                        "color": color
                    })

            if len(options) < 2:
                self.send_json(400, {"error": "At least 2 options are required for a poll"})
                return

            # Generate unique ID
            slug = slugify(question)
            short_hash = uuid.uuid4().hex[:6]
            poll_id = f"{slug}-{short_hash}"

            creator_token = (body.get("device_token") or "").strip()
            admin_key = "adm_" + uuid.uuid4().hex[:12]

            new_poll = {
                "id": poll_id,
                "question": question,
                "description": description,
                "created_at": get_now().strftime("%Y-%m-%d %H:%M"),
                "options": options,
                "votes": [],
                "creator_token": creator_token,
                "admin_key": admin_key,
                "admins": []
            }

            with data_lock:
                data = load_data()
                data["polls"][poll_id] = new_poll
                save_data(data)

            self.send_json(200, {
                "success": True,
                "id": poll_id,
                "vote_path": f"/p/{poll_id}",
                "results_path": f"/r/{poll_id}",
                "admin_key": admin_key,
                "message": "Poll created successfully!"
            })
            return

        # 2. Submit a vote to a poll
        if path.startswith("/api/vote/") or path == "/api/vote":
            poll_id = path[len("/api/vote/"):].strip("/") if path.startswith("/api/vote/") else (body.get("poll_id") or "").strip()
            name = (body.get("name") or "").strip()
            option_id = (body.get("option_id") or "").strip()
            comment = (body.get("comment") or "").strip()
            device_token = (body.get("device_token") or "").strip()

            if not poll_id:
                self.send_json(400, {"error": "Poll ID is required"})
                return
            if not name:
                self.send_json(400, {"error": "Name is required"})
                return
            if not option_id:
                self.send_json(400, {"error": "Option selection is required"})
                return

            with data_lock:
                data = load_data()
                polls = data.get("polls", {})
                if poll_id not in polls:
                    self.send_json(404, {"error": "Poll not found"})
                    return

                poll = polls[poll_id]
                opt_label = next((opt["label"] for opt in poll.get("options", []) if opt["id"] == option_id), None)
                if not opt_label:
                    self.send_json(400, {"error": "Invalid option selected"})
                    return

                votes = poll.get("votes", [])
                now_str = get_now_str()

                # Upsert by voter name (case-insensitive)
                existing = None
                for v in votes:
                    if v.get("voter_name", "").strip().lower() == name.lower():
                        existing = v
                        break

                if existing:
                    existing_token = existing.get("device_token")
                    # If this voter name is locked to another device, reject overwrite
                    if existing_token and device_token and existing_token != device_token:
                        self.send_json(403, {
                            "error": f"A response for '{name}' was already submitted from another device. Please enter your own name to vote."
                        })
                        return

                    existing["option_id"] = option_id
                    existing["option_label"] = opt_label
                    existing["comment"] = comment
                    existing["voted_at"] = now_str
                    if device_token:
                        existing["device_token"] = device_token
                    action = "updated"
                else:
                    new_vote = {
                        "voter_name": name,
                        "option_id": option_id,
                        "option_label": opt_label,
                        "comment": comment,
                        "voted_at": now_str
                    }
                    if device_token:
                        new_vote["device_token"] = device_token
                    votes.append(new_vote)
                    action = "recorded"

                poll["votes"] = votes
                save_data(data)

            self.send_json(200, {
                "success": True,
                "action": action,
                "message": f"Thanks {name}! Your response has been {action}.",
                "choice": opt_label
            })
            return

        # 3. Edit a poll (Question, Description, Options) - Creator & Admins only
        if path.startswith("/api/poll/") and path.endswith("/edit"):
            poll_id = path[len("/api/poll/"): -len("/edit")].strip("/")
            with data_lock:
                data = load_data()
                poll = data.get("polls", {}).get(poll_id)
                if not poll:
                    self.send_json(404, {"error": "Poll not found"})
                    return

                device_token = (body.get("device_token") or "").strip() or self.headers.get("X-Device-Token")
                admin_key = (body.get("admin_key") or body.get("key") or "").strip() or self.headers.get("X-Admin-Key")

                if not is_poll_admin(poll, device_token, admin_key):
                    self.send_json(403, {"error": "Unauthorized: Only poll creator or co-admins can edit this poll."})
                    return

                question = (body.get("question") or "").strip()
                description = (body.get("description") or "").strip()
                raw_options = body.get("options", [])

                if not question:
                    self.send_json(400, {"error": "Question is required"})
                    return
                if len(raw_options) < 2:
                    self.send_json(400, {"error": "At least 2 options are required"})
                    return

                poll["question"] = question
                poll["description"] = description

                palette = ["#10b981", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
                updated_options = []
                new_opt_map = {}

                for idx, opt in enumerate(raw_options):
                    oid = (opt.get("id") if isinstance(opt, dict) else "").strip() or f"opt-{idx+1}"
                    lbl = (opt.get("label") if isinstance(opt, dict) else str(opt)).strip()
                    color = opt.get("color") if isinstance(opt, dict) and opt.get("color") else palette[idx % len(palette)]
                    if lbl:
                        updated_options.append({
                            "id": oid,
                            "label": lbl,
                            "color": color
                        })
                        new_opt_map[oid] = lbl

                poll["options"] = updated_options

                # Update existing votes if their chosen option label was edited
                for v in poll.get("votes", []):
                    oid = v.get("option_id")
                    if oid in new_opt_map:
                        v["option_label"] = new_opt_map[oid]

                save_data(data)

            self.send_json(200, {"success": True, "message": "Poll updated successfully!"})
            return

        # 4. Remove an individual vote - Creator & Admins only
        if path.startswith("/api/poll/") and path.endswith("/vote/remove"):
            poll_id = path[len("/api/poll/"): -len("/vote/remove")].strip("/")
            with data_lock:
                data = load_data()
                poll = data.get("polls", {}).get(poll_id)
                if not poll:
                    self.send_json(404, {"error": "Poll not found"})
                    return

                device_token = (body.get("device_token") or "").strip() or self.headers.get("X-Device-Token")
                admin_key = (body.get("admin_key") or body.get("key") or "").strip() or self.headers.get("X-Admin-Key")

                if not is_poll_admin(poll, device_token, admin_key):
                    self.send_json(403, {"error": "Unauthorized: Only poll creator or co-admins can remove votes."})
                    return

                voter_name = (body.get("voter_name") or "").strip()
                if not voter_name:
                    self.send_json(400, {"error": "Voter name is required"})
                    return

                poll["votes"] = [
                    v for v in poll.get("votes", [])
                    if v.get("voter_name", "").strip().lower() != voter_name.lower()
                ]

                # Also remove from co-admins if they were an admin
                poll["admins"] = [
                    a for a in poll.get("admins", [])
                    if (a.get("voter_name", "").lower() if isinstance(a, dict) else str(a).lower()) != voter_name.lower()
                ]

                save_data(data)

            self.send_json(200, {"success": True, "message": f"Vote for '{voter_name}' has been removed."})
            return

        # 5. Toggle Co-Admin access for someone on the voter list - Creator & Admins only
        if path.startswith("/api/poll/") and path.endswith("/admins/toggle"):
            poll_id = path[len("/api/poll/"): -len("/admins/toggle")].strip("/")
            with data_lock:
                data = load_data()
                poll = data.get("polls", {}).get(poll_id)
                if not poll:
                    self.send_json(404, {"error": "Poll not found"})
                    return

                device_token = (body.get("device_token") or "").strip() or self.headers.get("X-Device-Token")
                admin_key = (body.get("admin_key") or body.get("key") or "").strip() or self.headers.get("X-Admin-Key")

                if not is_poll_admin(poll, device_token, admin_key):
                    self.send_json(403, {"error": "Unauthorized: Only poll creator or existing admins can manage admin access."})
                    return

                voter_name = (body.get("voter_name") or "").strip()
                if not voter_name:
                    self.send_json(400, {"error": "Voter name is required"})
                    return

                target_vote = next(
                    (v for v in poll.get("votes", []) if v.get("voter_name", "").strip().lower() == voter_name.lower()),
                    None
                )
                target_token = target_vote.get("device_token") if target_vote else None

                admins = poll.get("admins", [])
                already_admin = False
                for adm in admins:
                    adm_name = adm.get("voter_name") if isinstance(adm, dict) else adm
                    if adm_name and adm_name.lower() == voter_name.lower():
                        already_admin = True
                        break

                if already_admin:
                    poll["admins"] = [
                        a for a in admins
                        if (a.get("voter_name", "").lower() if isinstance(a, dict) else str(a).lower()) != voter_name.lower()
                    ]
                    is_admin_now = False
                    msg = f"Removed admin access from {voter_name}."
                else:
                    poll["admins"].append({
                        "voter_name": voter_name,
                        "device_token": target_token
                    })
                    is_admin_now = True
                    msg = f"Granted admin access to {voter_name}!"

                save_data(data)

            self.send_json(200, {
                "success": True,
                "is_admin": is_admin_now,
                "message": msg
            })
            return

        # 6. Reset votes for a specific poll
        if path.startswith("/api/poll/") and path.endswith("/reset"):
            poll_id = path[len("/api/poll/"): -len("/reset")].strip("/")
            with data_lock:
                data = load_data()
                if poll_id in data.get("polls", {}):
                    data["polls"][poll_id]["votes"] = []
                    save_data(data)
                    self.send_json(200, {"success": True, "message": "Votes cleared!"})
                    return
            self.send_json(404, {"error": "Poll not found"})
            return

        # 7. Delete a poll - Creator & Admins only
        if path.startswith("/api/poll/") and path.endswith("/delete"):
            poll_id = path[len("/api/poll/"): -len("/delete")].strip("/")
            with data_lock:
                data = load_data()
                poll = data.get("polls", {}).get(poll_id)
                if not poll:
                    self.send_json(404, {"error": "Poll not found"})
                    return

                device_token = (body.get("device_token") or "").strip() or self.headers.get("X-Device-Token")
                admin_key = (body.get("admin_key") or body.get("key") or "").strip() or self.headers.get("X-Admin-Key")

                if not is_poll_creator(poll, device_token, admin_key):
                    self.send_json(403, {"error": "Unauthorized: Only poll creator can delete this poll."})
                    return

                del data["polls"][poll_id]
                save_data(data)
                self.send_json(200, {"success": True, "message": "Poll deleted!"})
                return

        self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        try:
            client_ip = self.address_string()
        except Exception:
            client_ip = "client"
        sys.stderr.write(f"[{get_now().strftime('%H:%M:%S')}] {client_ip} - {msg}\n")

def run():
    port = int(os.environ.get("PORT", PORT))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    load_data()
    server = HTTPServer(("0.0.0.0", port), DynamicPollHandler)
    print(f"🚀 Dynamic Team Poll App running at http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == "__main__":
    run()
