import { Component, lazy, Suspense, useState } from "react";
import type { ReactNode } from "react";
import type { TownMapProps } from "./LeafletMap";
import { Notice } from "./Results";
import "leaflet/dist/leaflet.css";
const LeafletMap = lazy(() => import("./LeafletMap"));
class MapBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <Notice>
        Interactive map unavailable. The verified text selectors below retain
        full location-selection and retrieval functionality.
      </Notice>
    ) : (
      this.props.children
    );
  }
}
export default function TownMap(props: TownMapProps) {
  const [failure, setFailure] = useState(false);
  return (
    <>
      <MapBoundary>
        <Suspense
          fallback={
            <Notice>
              Loading interactive map… Text selectors remain available.
            </Notice>
          }
        >
          <LeafletMap {...props} onTileFailure={() => setFailure(true)} />
        </Suspense>
      </MapBoundary>
      {failure && (
        <Notice>
          Basemap tiles unavailable. Verified town coordinates and the
          accessible selectors below remain usable.
        </Notice>
      )}
      <p className="muted">
        Map: React Leaflet and Leaflet; © OpenStreetMap contributors (ODbL).
        Green markers are selected; gray markers are unselected. Town points
        only, no interpolation, spatial averages or hazard map. Markers support
        Enter/Space; text selectors provide the same actions. Pan or use the
        zoom controls to explore.
      </p>
    </>
  );
}
