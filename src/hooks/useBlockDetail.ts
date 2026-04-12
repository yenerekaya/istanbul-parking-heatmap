import { useState, useEffect } from "react";
import type { BlockDetail } from "../types";

/**
 * For Istanbul/İSPARK, block detail comes from the pre-loaded parking_week.json.
 * No on-demand API call needed — we reshape the block's own slots data.
 */
export function useBlockDetail(
  blockId: string | null,
  meters: number,
  street: string,
) {
  const [detail, setDetail] = useState<BlockDetail | null>(null);
  const [loading] = useState(false);
  const [error] = useState<string | null>(null);

  useEffect(() => {
    if (!blockId) {
      setDetail(null);
      return;
    }

    // Detail will be populated from the block's own pre-loaded slots
    // via the parent component. We just set a placeholder here.
    setDetail({
      blockId,
      street,
      meters,
      slots: new Array(168).fill(0),
      sessionCounts: new Array(168).fill(0),
    });
  }, [blockId, meters, street]);

  return { detail, loading, error };
}
