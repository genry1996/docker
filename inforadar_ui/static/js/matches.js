let previousData = [];

function showShimmer() {
  const table = document.getElementById("matches-table");
  table.innerHTML = `
    <div class="shimmer-container">
      <div class="shimmer shimmer-line" style="width:90%;height:20px"></div>
      <div class="shimmer shimmer-line" style="width:70%;height:20px"></div>
      <div class="shimmer shimmer-line" style="width:85%;height:20px"></div>
    </div>`;
}

async function loadMatches() {
  showShimmer();
  try {
    const response = await fetch("/api/matches");
    const data = await response.json();
    setTimeout(() => renderTable(data), 500);
  } catch (err) {
    console.error("Ошибка загрузки:", err);
  }
}

function rowClassByStatus(status) {
  switch (status) {
    case "suspended": return "status-suspended";
    case "limited": return "status-limited";
    case "removed": return "status-removed";
    default: return "";
  }
}

function renderTable(matches) {
  const table = document.getElementById("matches-table");
  if (!matches || matches.length === 0) {
    table.innerHTML = "<p>Нет матчей</p>";
    return;
  }

  let html = `
    <table class="fade-in-table">
      <thead>
        <tr>
          <th>Спорт</th>
          <th>Лига</th>
          <th>Дом</th>
          <th>Гости</th>
          <th>Кэф (Дом)</th>
          <th>Кэф (Гости)</th>
          <th>Счёт</th>
          <th>Время</th>
        </tr>
      </thead><tbody>`;

  matches.forEach((m, i) => {
    const cls = rowClassByStatus(m.status);
    html += `
      <tr id="match-${m.id}" class="${cls}">
        <td>${m.sport}</td>
        <td>${m.league}</td>
        <td>${m.home_team}</td>
        <td>${m.away_team}</td>
        <td class="odds-home">${m.odds_home ?? "-"}</td>
        <td class="odds-away">${m.odds_away ?? "-"}</td>
        <td>${m.score_home ?? "-"} : ${m.score_away ?? "-"}</td>
        <td>${m.start_time}</td>
      </tr>`;
  });
  html += "</tbody></table>";
  table.innerHTML = html;

  highlightChanges(matches);
}

function highlightChanges(newData) {
  newData.forEach((m, i) => {
    const old = previousData.find(o => o.id === m.id);
    if (!old) return;

    const homeCell = document.querySelector(`#match-${m.id} .odds-home`);
    const awayCell = document.querySelector(`#match-${m.id} .odds-away`);

    if (m.odds_home !== old.odds_home) {
      const color = m.odds_home > old.odds_home ? "#d9fdd3" : "#ffd6d6";
      homeCell.style.backgroundColor = color;
      setTimeout(() => homeCell.style.backgroundColor = "", 1200);
    }
    if (m.odds_away !== old.odds_away) {
      const color = m.odds_away > old.odds_away ? "#d9fdd3" : "#ffd6d6";
      awayCell.style.backgroundColor = color;
      setTimeout(() => awayCell.style.backgroundColor = "", 1200);
    }
  });
  previousData = JSON.parse(JSON.stringify(newData));
}

loadMatches();
setInterval(loadMatches, 10000);
