import Box from "@mui/material/Box";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import { PieChart } from "@mui/x-charts/PieChart";
import type { Allocation, Slice } from "../allocation";
import { money } from "../format";
import { useState } from "react";
import type { ReactElement, ReactNode } from "react";

/**
 * Categorical hues in a fixed order, validated for color-vision deficiency on
 * adjacent pairs; dark mode has its own steps rather than an automatic flip.
 */
const SERIES = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
} as const;

/** Cash and folded "other" slices: present, but not an entity to tell apart. */
const NEUTRAL = { light: "#b5b4ad", dark: "#6b6a65" } as const;

const SIZE = 180;
const SERIES_ID = "allocation";

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/**
 * One donut with its legend. The legend is the readable half: every slice's
 * exact amount and share, keyboard reachable, and the click target for
 * drilling in — the arcs only mirror it.
 */
export default function AllocationDonut({
  title,
  allocation,
  onOpen,
  empty = "Nothing to show",
}: {
  title: ReactNode;
  allocation: Allocation;
  /** Called with a drillable slice's key, from the arc or its legend row. */
  onOpen?: (key: string) => void;
  empty?: string;
}): ReactElement {
  const theme = useTheme();
  const mode = theme.palette.mode;
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const { slices, excluded } = allocation;
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  const color = (slice: Slice): string =>
    slice.slot === null ? NEUTRAL[mode] : (SERIES[mode][slice.slot % SERIES[mode].length] ?? NEUTRAL[mode]);
  const share = (slice: Slice): string => percent.format(slice.value / total);
  const open = (slice: Slice | undefined): void => {
    if (slice?.drillable && onOpen) {
      onOpen(slice.key);
    }
  };
  const canOpen = onOpen !== undefined && slices.some((slice) => slice.drillable);

  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="subtitle2" component="div" sx={{ mb: 1 }}>
        {title}
      </Typography>
      {slices.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {empty}
        </Typography>
      ) : (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <Box sx={{ flexShrink: 0 }}>
            <PieChart
              width={SIZE}
              height={SIZE}
              margin={0}
              hideLegend
              highlightedItem={
                highlighted === null ? null : { seriesId: SERIES_ID, dataIndex: highlighted }
              }
              onHighlightChange={(item) => setHighlighted(item?.dataIndex ?? null)}
              onItemClick={(_event, item) => open(slices[item.dataIndex])}
              series={[
                {
                  id: SERIES_ID,
                  data: slices.map((slice) => ({
                    id: slice.key,
                    value: slice.value,
                    label: slice.label,
                    color: color(slice),
                  })),
                  innerRadius: SIZE * 0.3,
                  outerRadius: SIZE * 0.46,
                  paddingAngle: 1,
                  cornerRadius: 3,
                  highlightScope: { highlight: "item", fade: "global" },
                  highlighted: { additionalRadius: 4 },
                  valueFormatter: (_value, { dataIndex }) => {
                    const slice = slices[dataIndex];
                    return slice ? `${money(slice.amount)} · ${share(slice)}` : null;
                  },
                },
              ]}
              {...(canOpen && { sx: { "& .MuiPieArc-root": { cursor: "pointer" } } })}
            />
          </Box>
          <List dense disablePadding sx={{ flexGrow: 1, minWidth: 0, width: "100%", maxWidth: 440 }}>
            {slices.map((slice, index) => {
              const row = (
                <Stack direction="row" alignItems="center" spacing={1} sx={{ width: "100%" }}>
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: "2px",
                      flexShrink: 0,
                      backgroundColor: color(slice),
                    }}
                  />
                  <Typography variant="body2" noWrap sx={{ flexGrow: 1, minWidth: 0 }}>
                    {slice.label}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {share(slice)}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontVariantNumeric: "tabular-nums", textAlign: "right" }}
                  >
                    {money(slice.amount)}
                  </Typography>
                  {canOpen && (
                    <ChevronRightIcon
                      fontSize="small"
                      sx={{ visibility: slice.drillable ? "visible" : "hidden" }}
                    />
                  )}
                </Stack>
              );
              const hover = {
                onMouseEnter: () => setHighlighted(index),
                onMouseLeave: () => setHighlighted(null),
              };
              return slice.drillable && onOpen ? (
                <ListItemButton
                  key={slice.key}
                  selected={highlighted === index}
                  onClick={() => open(slice)}
                  onFocus={() => setHighlighted(index)}
                  onBlur={() => setHighlighted(null)}
                  aria-label={`Show ${slice.label} holdings`}
                  sx={{ borderRadius: 1, py: 0.25, px: 1 }}
                  {...hover}
                >
                  {row}
                </ListItemButton>
              ) : (
                <ListItem
                  key={slice.key}
                  sx={{
                    borderRadius: 1,
                    py: 0.25,
                    px: 1,
                    backgroundColor: highlighted === index ? "action.hover" : undefined,
                  }}
                  {...hover}
                >
                  {row}
                </ListItem>
              );
            })}
          </List>
        </Stack>
      )}
      {excluded.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
          Not drawn, since a slice cannot be negative:{" "}
          {excluded.map((item) => `${item.label} ${money(item.amount)}`).join(", ")}. Shares are
          of the positive amounts above.
        </Typography>
      )}
    </Box>
  );
}
