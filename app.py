from flask import Flask, render_template_string, request, session
from flask_socketio import SocketIO, emit
import random
import threading
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = "auction_secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# -----------------------------
# SETTINGS
# -----------------------------
STARTING_PURSE = 10000
BID_INCREMENT = 100
HOST_PASSWORD = "pra123"
AI_BOTS_ENABLED = True
AI_BOT_TEAMS = ["Team D"]

# -----------------------------
# AUCTION DATA
# -----------------------------
teams = {
    "Team A": {"purse": STARTING_PURSE, "players": []},
    "Team B": {"purse": STARTING_PURSE, "players": []},
    "Team C": {"purse": STARTING_PURSE, "players": []},
    "Team D": {"purse": STARTING_PURSE, "players": []},
}

players = [
    {"name": "Virat", "base": 1000, "category": "Marquee"},
    {"name": "Rohit", "base": 900, "category": "Batter"},
    {"name": "Bumrah", "base": 1200, "category": "Bowler"},
    {"name": "Hardik", "base": 1100, "category": "All Rounder"},
    {"name": "Dhoni", "base": 1500, "category": "Wicket Keeper"},
    {"name": "Maxwell", "base": 800, "category": "All Rounder"},
]

current_index = 0
current_bid = players[0]["base"]
highest_team = None
sold_players = []

# -----------------------------
# CSS
# -----------------------------
COMMON_STYLE = """
<style>
body { margin:0; font-family:Arial,sans-serif; background:#111827; color:white; }
.header { background:#020617; padding:18px; text-align:center; font-size:30px; font-weight:bold; color:#38bdf8; }
.container { display:grid; grid-template-columns:1fr 2fr 1fr; gap:18px; padding:18px; }
.card { background:#1f2937; padding:18px; border-radius:16px; box-shadow:0 0 15px rgba(0,0,0,.4); }
h2,h3 { color:#facc15; }
.player-box { text-align:center; background:#0f172a; border:2px solid #38bdf8; border-radius:16px; padding:25px; }
.player-name { font-size:42px; font-weight:bold; color:#22c55e; }
.bid { font-size:34px; color:#f97316; margin:15px; transition:0.2s ease; }
.purse { color:#22c55e; font-weight:bold; transition:0.3s ease; }
button { border:0; padding:12px 18px; margin:7px; border-radius:10px; font-size:16px; cursor:pointer; font-weight:bold; }
.bid-btn { background:#2563eb; color:white; }
.sold-btn { background:#16a34a; color:white; }
.unsold-btn { background:#dc2626; color:white; }
.reset-btn { background:#9333ea; color:white; }
.join-btn { background:#facc15; color:#111827; }
.bot-btn { background:#fb923c; color:#111827; }
select,input { padding:10px; border-radius:8px; border:0; margin:5px; font-size:16px; }
table { width:100%; border-collapse:collapse; margin-top:10px; }
th,td { border:1px solid #374151; padding:8px; text-align:center; }
th { background:#020617; color:#38bdf8; }
.team-card { background:#111827; padding:10px; border-radius:10px; margin-bottom:10px; }
.small { color:#cbd5e1; font-size:14px; }
.warning { color:#fb7185; font-weight:bold; }
.success { color:#22c55e; font-weight:bold; }
@keyframes pop { 0%{transform:scale(1)} 50%{transform:scale(1.18)} 100%{transform:scale(1)} }
.pop { animation:pop 0.25s ease; }
@media(max-width:800px){ .container{grid-template-columns:1fr;} .player-name{font-size:32px;} }
</style>
"""

# -----------------------------
# LOGIN PAGE
# -----------------------------
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Host Login</title>
{{ style|safe }}
</head>
<body>
<div class="header">🔐 Host Login</div>
<div class="card" style="max-width:420px;margin:80px auto;text-align:center;">
    <h2>Enter Admin Password</h2>
    <form method="post">
        <input name="password" type="password" placeholder="Password">
        <br><br>
        <button class="join-btn">Login</button>
    </form>
    <p class="warning">{{ error }}</p>
    <p class="small">Default password: pra123</p>
</div>
</body>
</html>
"""

# -----------------------------
# HOST PAGE
# -----------------------------
HOST_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Auction Host</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
{{ style|safe }}
</head>
<body>
<div class="header">🎤 Host / Auctioneer Screen</div>

<div class="container">
    <div class="card">
        <h2>Team Squad Tables</h2>
        <div id="teamsBox"></div>
    </div>

    <div class="card player-box">
        <p id="category"></p>
        <div class="player-name" id="playerName">Loading...</div>
        <p id="basePrice"></p>
        <div class="bid" id="currentBid"></div>
        <h3 id="highestBidder"></h3>

        <h3>Host Controls</h3>
        <button class="sold-btn" onclick="soldPlayer()">SOLD</button>
        <button class="unsold-btn" onclick="unsoldPlayer()">UNSOLD</button>
        <button class="reset-btn" onclick="resetAuction()">RESET</button>
        <button class="bot-btn" onclick="botBid()">AI BOT BID</button>
        <p class="small">Teams only bid. Host controls SOLD / UNSOLD / RESET.</p>
    </div>

    <div class="card">
        <h2>Auction Board</h2>
        <table>
            <thead><tr><th>Player</th><th>Team</th><th>Price</th></tr></thead>
            <tbody id="board"></tbody>
        </table>
    </div>
</div>

<audio id="bidSound">
    <source src="https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg" type="audio/ogg">
</audio>

<script>
const socket = io();
let lastBid = 0;

function soldPlayer(){ socket.emit("sold_player"); }
function unsoldPlayer(){ socket.emit("unsold_player"); }
function botBid(){ socket.emit("ai_bot_bid"); }
function resetAuction(){ if(confirm("Reset auction?")){ socket.emit("reset_auction"); } }

socket.on("update", function(data){ updateScreen(data); });

function playBidSound(data){
    if(data.current_bid !== lastBid){
        let s = document.getElementById("bidSound");
        s.currentTime = 0;
        s.play().catch(()=>{});
        lastBid = data.current_bid;
    }
}

function pop(id){
    let el = document.getElementById(id);
    el.classList.remove("pop");
    void el.offsetWidth;
    el.classList.add("pop");
}

function updateScreen(data){
    if(data.player){
        document.getElementById("category").innerText = "Category: " + data.player.category;
        document.getElementById("playerName").innerText = data.player.name;
        document.getElementById("basePrice").innerText = "Base Price: ₹" + data.player.base;
        document.getElementById("currentBid").innerText = "Current Bid: ₹" + data.current_bid;
        document.getElementById("highestBidder").innerText = "Highest Bidder: " + (data.highest_team || "No bid yet");
        pop("currentBid");
        playBidSound(data);
    } else {
        document.getElementById("category").innerText = "";
        document.getElementById("playerName").innerText = "Auction Finished 🎉";
        document.getElementById("basePrice").innerText = "";
        document.getElementById("currentBid").innerText = "";
        document.getElementById("highestBidder").innerText = "";
    }

    let teamsHTML = "";
    for(let team in data.teams){
        teamsHTML += `<div class='team-card'>
            <h3>${team}</h3>
            <p class='purse'>Remaining Purse: ₹${data.teams[team].purse}</p>
            <p>Players Bought: ${data.teams[team].players.length}</p>
            <p><b>Squad:</b> ${data.teams[team].players.join(", ") || "No players yet"}</p>
        </div>`;
    }
    document.getElementById("teamsBox").innerHTML = teamsHTML;

    let boardHTML = "";
    data.sold_players.forEach(item => {
        boardHTML += `<tr><td>${item.player}</td><td>${item.team}</td><td>₹${item.price}</td></tr>`;
    });
    document.getElementById("board").innerHTML = boardHTML;
}
</script>
</body>
</html>
"""

# -----------------------------
# SPECTATOR PAGE
# -----------------------------
SPECTATOR_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Spectator Mode</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
{{ style|safe }}
</head>
<body>
<div class="header">👀 Spectator Mode</div>

<div class="container">
    <div class="card">
        <h2>Live Teams</h2>
        <div id="teamsBox"></div>
    </div>

    <div class="card player-box">
        <p id="category"></p>
        <div class="player-name" id="playerName">Loading...</div>
        <p id="basePrice"></p>
        <div class="bid" id="currentBid"></div>
        <h3 id="highestBidder"></h3>
        <p class="small">Spectators can only watch the auction live.</p>
    </div>

    <div class="card">
        <h2>Auction Board</h2>
        <table>
            <thead><tr><th>Player</th><th>Team</th><th>Price</th></tr></thead>
            <tbody id="board"></tbody>
        </table>
    </div>
</div>

<script>
const socket = io();

socket.on("update", function(data){
    if(data.player){
        document.getElementById("category").innerText = "Category: " + data.player.category;
        document.getElementById("playerName").innerText = data.player.name;
        document.getElementById("basePrice").innerText = "Base Price: ₹" + data.player.base;
        document.getElementById("currentBid").innerText = "Current Bid: ₹" + data.current_bid;
        document.getElementById("highestBidder").innerText = "Highest Bidder: " + (data.highest_team || "No bid yet");
    }

    let teamsHTML = "";
    for(let team in data.teams){
        teamsHTML += `<div class='team-card'>
            <h3>${team}</h3>
            <p class='purse'>Remaining Purse: ₹${data.teams[team].purse}</p>
            <p>Players Bought: ${data.teams[team].players.length}</p>
        </div>`;
    }
    document.getElementById("teamsBox").innerHTML = teamsHTML;

    let boardHTML = "";
    data.sold_players.forEach(item => {
        boardHTML += `<tr><td>${item.player}</td><td>${item.team}</td><td>₹${item.price}</td></tr>`;
    });
    document.getElementById("board").innerHTML = boardHTML;
});
</script>
</body>
</html>
"""

# -----------------------------
# TEAM PAGE
# -----------------------------
TEAM_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Auction Team</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
{{ style|safe }}
</head>
<body>
<div class="header">🏏 Team Bidding Screen</div>

<div class="container">
    <div class="card">
        <h2>Join Team</h2>
        <select id="teamSelect">
            <option value="Team A">Team A</option>
            <option value="Team B">Team B</option>
            <option value="Team C">Team C</option>
            <option value="Team D">Team D</option>
        </select>
        <button class="join-btn" onclick="joinTeam()">Join</button>
        <p>You joined as: <b id="myTeam">Not joined</b></p>
        <p class="warning" id="message">Connecting to server...</p>
        <h2>Your Squad</h2>
        <div id="myTeamBox"></div>
    </div>

    <div class="card player-box">
        <p id="category"></p>
        <div class="player-name" id="playerName">Loading...</div>
        <p id="basePrice"></p>
        <div class="bid" id="currentBid"></div>
        <h3 id="highestBidder"></h3>
        <button class="bid-btn" onclick="placeBid()">BID + ₹100</button>
        <p class="small">Host controls sold/unsold. You can only bid.</p>
    </div>

    <div class="card">
        <h2>Auction Board</h2>
        <table>
            <thead><tr><th>Player</th><th>Team</th><th>Price</th></tr></thead>
            <tbody id="board"></tbody>
        </table>
    </div>
</div>

<audio id="bidSound">
    <source src="https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg" type="audio/ogg">
</audio>

<script>
const socket = io();
let myTeam = null;
let latestData = null;
let lastBid = 0;

socket.on("connect", function(){
    document.getElementById("message").innerText = "Connected to auction server";
});

socket.on("connect_error", function(){
    document.getElementById("message").innerText = "Server not connected. Refresh or check terminal.";
});

function joinTeam(){
    myTeam = document.getElementById("teamSelect").value;
    document.getElementById("myTeam").innerText = myTeam;
    document.getElementById("message").innerText = "Joined successfully";
    if(latestData) updateScreen(latestData);
}

function placeBid(){
    if(!myTeam){
        document.getElementById("message").innerText = "First select team and click Join";
        return;
    }
    socket.emit("place_bid", {team: myTeam});
}

socket.on("update", function(data){
    latestData = data;
    updateScreen(data);
});

socket.on("bid_error", function(data){
    document.getElementById("message").innerText = data.message;
});

function playBidSound(data){
    if(data.current_bid !== lastBid){
        let s = document.getElementById("bidSound");
        s.currentTime = 0;
        s.play().catch(()=>{});
        lastBid = data.current_bid;
    }
}

function pop(id){
    let el = document.getElementById(id);
    el.classList.remove("pop");
    void el.offsetWidth;
    el.classList.add("pop");
}

function updateScreen(data){
    if(data.player){
        document.getElementById("category").innerText = "Category: " + data.player.category;
        document.getElementById("playerName").innerText = data.player.name;
        document.getElementById("basePrice").innerText = "Base Price: ₹" + data.player.base;
        document.getElementById("currentBid").innerText = "Current Bid: ₹" + data.current_bid;
        document.getElementById("highestBidder").innerText = "Highest Bidder: " + (data.highest_team || "No bid yet");
        pop("currentBid");
        playBidSound(data);
    } else {
        document.getElementById("category").innerText = "";
        document.getElementById("playerName").innerText = "Auction Finished 🎉";
        document.getElementById("basePrice").innerText = "";
        document.getElementById("currentBid").innerText = "";
        document.getElementById("highestBidder").innerText = "";
    }

    if(myTeam && data.teams[myTeam]){
        let t = data.teams[myTeam];
        document.getElementById("myTeamBox").innerHTML = `
        <div class='team-card'>
            <h3>${myTeam}</h3>
            <p class='purse'>Remaining Purse: ₹${t.purse}</p>
            <p><b>Squad:</b> ${t.players.join(", ") || "No players yet"}</p>
            <p>Total Players: ${t.players.length}</p>
        </div>`;
    }

    let boardHTML = "";
    data.sold_players.forEach(item => {
        boardHTML += `<tr><td>${item.player}</td><td>${item.team}</td><td>₹${item.price}</td></tr>`;
    });
    document.getElementById("board").innerHTML = boardHTML;
}
</script>
</body>
</html>
"""

# -----------------------------
# HELPERS
# -----------------------------
def get_state():
    player = players[current_index] if current_index < len(players) else None
    return {
        "teams": teams,
        "player": player,
        "current_bid": current_bid,
        "highest_team": highest_team,
        "sold_players": sold_players,
    }

def send_update():
    socketio.emit("update", get_state())

def bot_bid_logic():
    global current_bid, highest_team

    if current_index >= len(players):
        return

    time.sleep(random.uniform(0.8, 1.8))
    next_bid = current_bid + BID_INCREMENT

    possible_bots = []
    for bot_team in AI_BOT_TEAMS:
        if bot_team in teams and teams[bot_team]["purse"] >= next_bid:
            possible_bots.append(bot_team)

    if possible_bots and random.randint(1, 100) <= 55:
        bot_team = random.choice(possible_bots)
        current_bid = next_bid
        highest_team = bot_team
        send_update()

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return """
    <h1>Online Auction Game</h1>
    <h2>Host:</h2><a href='/host'>/host</a>
    <h2>Team:</h2><a href='/team'>/team</a>
    <h2>Spectator:</h2><a href='/spectator'>/spectator</a>
    <p>Host password: pra123</p>
    """

@app.route("/host", methods=["GET", "POST"])
def host_page():
    if request.method == "POST":
        if request.form.get("password") == HOST_PASSWORD:
            session["host"] = True
            return render_template_string(HOST_HTML, style=COMMON_STYLE)
        return render_template_string(LOGIN_HTML, style=COMMON_STYLE, error="Wrong password")

    if session.get("host"):
        return render_template_string(HOST_HTML, style=COMMON_STYLE)

    return render_template_string(LOGIN_HTML, style=COMMON_STYLE, error="")

@app.route("/team")
def team_page():
    return render_template_string(TEAM_HTML, style=COMMON_STYLE)

@app.route("/spectator")
def spectator_page():
    return render_template_string(SPECTATOR_HTML, style=COMMON_STYLE)

# -----------------------------
# SOCKET EVENTS
# -----------------------------
@socketio.on("connect")
def connect():
    emit("update", get_state())

@socketio.on("place_bid")
def place_bid(data):
    global current_bid, highest_team

    team = data.get("team")

    if current_index >= len(players):
        emit("bid_error", {"message": "Auction is finished"})
        return

    if team not in teams:
        emit("bid_error", {"message": "Only Team A, B, C, D can bid"})
        return

    next_bid = current_bid + BID_INCREMENT

    if teams[team]["purse"] < next_bid:
        emit("bid_error", {"message": "Not enough purse to bid"})
        return

    current_bid = next_bid
    highest_team = team
    send_update()

    if AI_BOTS_ENABLED:
        threading.Thread(target=bot_bid_logic, daemon=True).start()

@socketio.on("ai_bot_bid")
def ai_bot_bid():
    threading.Thread(target=bot_bid_logic, daemon=True).start()

@socketio.on("sold_player")
def sold_player():
    global current_index, current_bid, highest_team

    if current_index >= len(players):
        send_update()
        return

    player = players[current_index]

    if highest_team:
        teams[highest_team]["purse"] -= current_bid
        teams[highest_team]["players"].append(player["name"])
        sold_players.append({"player": player["name"], "team": highest_team, "price": current_bid})
    else:
        sold_players.append({"player": player["name"], "team": "UNSOLD", "price": 0})

    current_index += 1
    current_bid = players[current_index]["base"] if current_index < len(players) else 0
    highest_team = None
    send_update()

@socketio.on("unsold_player")
def unsold_player():
    global current_index, current_bid, highest_team

    if current_index < len(players):
        player = players[current_index]
        sold_players.append({"player": player["name"], "team": "UNSOLD", "price": 0})

    current_index += 1
    current_bid = players[current_index]["base"] if current_index < len(players) else 0
    highest_team = None
    send_update()

@socketio.on("reset_auction")
def reset_auction():
    global teams, current_index, current_bid, highest_team, sold_players

    teams = {
        "Team A": {"purse": STARTING_PURSE, "players": []},
        "Team B": {"purse": STARTING_PURSE, "players": []},
        "Team C": {"purse": STARTING_PURSE, "players": []},
        "Team D": {"purse": STARTING_PURSE, "players": []},
    }
    current_index = 0
    current_bid = players[0]["base"]
    highest_team = None
    sold_players = []
    send_update()

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
