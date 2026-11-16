import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Tooltip,
  useMap,
} from "react-leaflet";
import type { CircleMarker as Marker } from "leaflet";
import type { TownPoint, Weather } from "./contracts";
import { formatMetric } from "./format";
export interface TownMapProps {
  towns: TownPoint[];
  selected: string[];
  onSelect: (id: string) => void;
  results?: Weather[];
  onTileFailure?: () => void;
}
function FitBounds({ towns }: { towns: TownPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (towns.length)
      map.fitBounds(
        towns.map((t) => [t.latitude, t.longitude] as [number, number]),
        { padding: [30, 30], maxZoom: 11 },
      );
  }, [map, towns]);
  return null;
}
export default function LeafletMap({
  towns,
  selected,
  onSelect,
  results = [],
  onTileFailure,
}: TownMapProps) {
  return (
    <MapContainer
      center={[27.4, 88.45]}
      zoom={9}
      scrollWheelZoom={false}
      className="town-map"
      aria-label="Interactive verified Sikkim town map"
    >
      <FitBounds towns={towns} />
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
        maxZoom={16}
        eventHandlers={{ tileerror: () => onTileFailure?.() }}
      />
      {towns.map((t) => {
        const active = selected.includes(t.id);
        const record = results.find((r) => r.location_id === t.id);
        const bind = (marker: Marker | null) => {
          const el = marker?.getElement();
          if (!el) return;
          el.setAttribute("tabindex", "0");
          el.setAttribute("role", "button");
          el.setAttribute("aria-label", `Map point ${t.name}`);
          el.setAttribute("aria-pressed", String(active));
          el.setAttribute("data-latitude", String(t.latitude));
          el.setAttribute("data-longitude", String(t.longitude));
          (el as SVGElement).onkeydown = (event: KeyboardEvent) => {
            const e = event as KeyboardEvent;
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onSelect(t.id);
            }
          };
        };
        return (
          <CircleMarker
            key={t.id}
            center={[t.latitude, t.longitude]}
            radius={active ? 10 : 7}
            pathOptions={{
              color: active ? "#04574f" : "#53758c",
              fillColor: active ? "#1dad83" : "#a5becb",
              fillOpacity: 0.95,
              weight: 2,
            }}
            ref={bind}
            eventHandlers={{
              click: () => onSelect(t.id),
              add: (event) => bind(event.target),
            }}
          >
            <Tooltip>
              <strong>{t.name}</strong>
              <br />
              {t.latitude}, {t.longitude}
              <br />
              {record ? (
                <>
                  {record.start} → {record.end}
                  <br />
                  {formatMetric(record.summary.temperature_mean_c, "°C")} °C ·{" "}
                  {formatMetric(record.summary.rainfall_total_mm, "mm")} mm
                  rainfall
                  <br />
                  Retrieved {record.retrieved_at} · {record.source}
                </>
              ) : (
                "No retrieved measurements for this point"
              )}
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
