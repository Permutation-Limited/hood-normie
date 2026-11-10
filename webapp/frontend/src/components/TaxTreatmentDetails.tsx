import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Collapse from "@mui/material/Collapse";
import Typography from "@mui/material/Typography";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import { useState } from "react";
import type { ReactElement, ReactNode } from "react";

/**
 * The attempted tax treatment, closed until asked for.
 *
 * Robinhood reports neither holding periods nor qualified status, so the
 * split into terms and rates is an inference that can be wrong. The totals
 * above it are not; keeping this folded stops a guess from reading as a fact.
 */
export default function TaxTreatmentDetails({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  const [open, setOpen] = useState(false);
  return (
    <Box sx={{ mt: 2 }}>
      <Button
        size="small"
        color="inherit"
        onClick={() => {
          setOpen(!open);
        }}
        aria-expanded={open}
        startIcon={open ? <KeyboardArrowDownIcon /> : <KeyboardArrowRightIcon />}
        sx={{ color: "text.secondary" }}
      >
        {open ? "Hide" : "Show"} estimated tax treatment
      </Button>
      <Collapse in={open} unmountOnExit>
        <Box sx={{ pt: 1 }}>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 2, maxWidth: 760 }}
          >
            A best guess, not a 1099. Holding periods are inferred assuming
            first-in-first-out sales, which a sale of specific lots breaks, and
            a dividend is qualified only where <code>income.yaml</code> says so.
          </Typography>
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}
