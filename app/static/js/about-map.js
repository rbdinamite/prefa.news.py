(function () {
  "use strict";

  const mapElement = document.getElementById("municipality-map");
  const statusElement = document.getElementById("map-status");
  if (!mapElement || !statusElement) return;

  const colors = {
    FECAM: "#16a34a",
    IPM: "#2563eb",
    PROPRIO: "#ea580c",
    inactive: "#a3a3a3",
  };

  function normalizeName(name) {
    return name.trim().toUpperCase();
  }

  function collectCoordinates(geometry, coordinates) {
    function walk(value) {
      if (typeof value[0] === "number" && typeof value[1] === "number") {
        coordinates.push(value);
        return;
      }
      value.forEach(walk);
    }
    walk(geometry.coordinates);
  }

  function pathForGeometry(geometry, project) {
    const rings = [];
    function addPolygon(polygon) {
      polygon.forEach((ring) => {
        if (!ring.length) return;
        const points = ring.map(project);
        rings.push(
          "M" + points.map((point) => point[0] + " " + point[1]).join("L") + "Z"
        );
      });
    }

    if (geometry.type === "Polygon") {
      addPolygon(geometry.coordinates);
    } else if (geometry.type === "MultiPolygon") {
      geometry.coordinates.forEach(addPolygon);
    }
    return rings.join("");
  }

  async function loadMap() {
    const cityByName = new Map(
      JSON.parse(mapElement.dataset.cities).map((city) => [normalizeName(city.name), city])
    );
    const response = await fetch("/static/geojson/sc-municipalities.geojson");
    if (!response.ok) {
      throw new Error("Municipality boundaries request failed: " + response.status);
    }
    const geojson = await response.json();
    const coordinates = [];
    geojson.features.forEach((feature) => collectCoordinates(feature.geometry, coordinates));
    if (!coordinates.length) {
      throw new Error("Municipality boundary data contains no coordinates.");
    }

    const centerLatitude = coordinates.reduce((sum, point) => sum + point[1], 0) / coordinates.length;
    const longitudeScale = Math.cos((centerLatitude * Math.PI) / 180);
    const projected = coordinates.map(([longitude, latitude]) => [
      longitude * longitudeScale,
      -latitude,
    ]);
    const bounds = projected.reduce(
      (result, point) => ({
        minX: Math.min(result.minX, point[0]),
        maxX: Math.max(result.maxX, point[0]),
        minY: Math.min(result.minY, point[1]),
        maxY: Math.max(result.maxY, point[1]),
      }),
      { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
    );
    const width = 1000;
    const height = 750;
    const padding = 12;
    const scale = Math.min(
      (width - padding * 2) / (bounds.maxX - bounds.minX),
      (height - padding * 2) / (bounds.maxY - bounds.minY)
    );
    const project = ([longitude, latitude]) => [
      padding + (longitude * longitudeScale - bounds.minX) * scale,
      padding + (-latitude - bounds.minY) * scale,
    ];

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Map of municipalities in Santa Catarina");

    geojson.features.forEach((feature) => {
      const name = feature.properties.name;
      if (!name) return;
      const city = cityByName.get(normalizeName(name));
      const isActive = Boolean(city && city.active);
      const urlType = isActive ? city.url_type.toUpperCase() : "";
      const color = isActive ? (colors[urlType] || colors.inactive) : colors.inactive;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathForGeometry(feature.geometry, project));
      path.setAttribute("fill", color);
      path.setAttribute("class", "municipality-map__city");
      path.setAttribute("aria-label", isActive ? name + ", " + urlType : name);
      path.setAttribute("tabindex", "0");
      const tooltip = document.createElementNS("http://www.w3.org/2000/svg", "title");
      tooltip.textContent = isActive ? name + " — " + urlType : name;
      path.appendChild(tooltip);
      svg.appendChild(path);
    });

    mapElement.replaceChildren(svg);
    statusElement.textContent = "";
  }

  loadMap().catch((error) => {
    console.error("Unable to load municipality map.", error);
    statusElement.textContent = "The municipality map could not be loaded. Please try again later.";
  });
})();
