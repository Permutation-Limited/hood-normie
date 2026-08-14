import FormControlLabel from "@mui/material/FormControlLabel";
import Switch from "@mui/material/Switch";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useNavigate } from "@tanstack/react-router";
import type { ReactElement } from "react";

/**
 * Toggles demo mode. The state is a URL search param rather than component
 * state, so a demo view can be linked, bookmarked, and survives a reload —
 * and so nothing can show demo numbers under a URL that claims to be live.
 */
export default function DemoSwitch({ demo }: { demo: boolean }): ReactElement {
  const navigate = useNavigate();
  return (
    <Tooltip title="Show invented portfolios instead of your Robinhood accounts">
      <FormControlLabel
        sx={{ mr: 0 }}
        control={
          <Switch
            size="small"
            checked={demo}
            onChange={(event) => {
              void navigate({
                to: ".",
                search: event.target.checked ? { demo: true } : {},
              });
            }}
            slotProps={{ input: { "aria-label": "Demo mode" } }}
          />
        }
        label={
          <Typography
            variant="body2"
            color="text.secondary"
            // The switch keeps its aria-label; on a phone the word costs the
            // nav tabs more room than it earns.
            sx={{ display: { xs: "none", sm: "block" } }}
          >
            Demo
          </Typography>
        }
      />
    </Tooltip>
  );
}
