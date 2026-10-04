/* Shared Chart.js helpers for insightboard. */

// dark-theme defaults so charts match the rest of the UI
if (window.Chart) {
  Chart.defaults.color = "#8b96b3";
  Chart.defaults.borderColor = "rgba(148, 163, 184, 0.12)";
  Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif';
}

var PALETTE = [
  "#38bdf8", "#818cf8", "#2dd4bf", "#fbbf24", "#f87171",
  "#a78bfa", "#34d399", "#fb923c", "#22d3ee", "#e879f9",
  "#94a3b8", "#facc15",
];

function palette(n) {
  var out = [];
  for (var i = 0; i < n; i++) out.push(PALETTE[i % PALETTE.length]);
  return out;
}

// data is the payload from /api/preview or /api/charts/<id>/data:
// either {labels, values} (bar/line/pie) or {points} (scatter)
function renderChart(canvas, type, title, data) {
  var datasets, labels = null;

  if (data.points) {
    datasets = [{
      label: title,
      data: data.points,
      backgroundColor: PALETTE[0],
      borderColor: PALETTE[0],
    }];
  } else {
    var colors = palette((data.labels || []).length);
    labels = data.labels;
    datasets = [{
      label: title,
      data: data.values,
      backgroundColor: type === "pie" ? colors : colors[0] + "cc",
      borderColor: type === "pie" ? "#182036" : colors[0],
      borderWidth: type === "pie" ? 2 : 1,
      fill: type === "line" ? false : undefined,
      tension: type === "line" ? 0.25 : undefined,
    }];
  }

  var options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: type === "pie", position: "right" },
      title: { display: true, text: title, color: "#e6ebf5", font: { size: 14, weight: "600" } },
    },
  };
  if (data.points) {
    options.scales = {
      x: { type: "linear", position: "bottom", title: { display: true, text: "x" } },
      y: { title: { display: true, text: "y" } },
    };
  }

  return new Chart(canvas, { type: type, data: { labels: labels, datasets: datasets }, options: options });
}
