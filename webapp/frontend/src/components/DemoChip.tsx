import Chip from "@mui/material/Chip";
import Tooltip from "@mui/material/Tooltip";
import ScienceIcon from "@mui/icons-material/Science";
import SensorsIcon from "@mui/icons-material/Sensors";
import { useNavigate } from "@tanstack/react-router";
import type { ReactElement } from "react";

/**
 * Which data the app is showing, and the toggle between the two.
 *
 * The chip always names the current state — "Demo data" or "Live data" — never
 * the state it would switch to, so a glance at the header answers "am I looking
 * at my own money?" without having to interpret a control. Demo is the
 * exceptional state and wears filled amber; live is a quiet outline.
 *
 * The state is a URL search param rather than component state, so a demo view
 * can be linked, bookmarked, and survives a reload — and so nothing can show
 * demo numbers under a URL that claims to be live.
 */
export default function DemoChip({ demo }: { demo: boolean }): ReactElement {
  const navigate = useNavigate();
  return (
    <Tooltip
      title={
        demo
          ? "Invented data. Click to switch to your live accounts."
          : "Your live Robinhood accounts. Click to switch to invented demo data."
      }
    >
      <Chip
        icon={demo ? <ScienceIcon /> : <SensorsIcon />}
        label={demo ? "Demo data" : "Live data"}
        size="small"
        color={demo ? "warning" : "default"}
        variant={demo ? "filled" : "outlined"}
        aria-pressed={demo}
        onClick={() => {
          // Omitted rather than false, to keep a live URL free of query noise.
          void navigate({ to: ".", search: demo ? {} : { demo: true } });
        }}
      />
    </Tooltip>
  );
}
