import { observer } from "mobx-react-lite";
import { Button, Container, Stack, Text, Title } from "@mantine/core";
import { Link as RouterLink } from "react-router-dom";

/**
 * The admin SPA's `path="*"` page (defect 7: an unknown `/admin/xyz` used to
 * render the header plus a blank body).
 *
 * No props, no state, no `useEffect`, no data load. Renders its own
 * `<Container size="lg" py="md">` (consistent with the three real pages) holding a
 * heading, a dimmed explanation, and a Mantine `Button component={RouterLink}
 * to="/"` back to Users — a **router** link here, correctly, because this is
 * in-SPA navigation and must respect `basename`.
 */
export const NotFoundPage = observer(function NotFoundPage() {
  return (
    <Container size="lg" py="md">
      <Stack align="flex-start" gap="sm">
        <Title order={3}>Page not found</Title>
        <Text c="dimmed">
          This admin address does not exist. The link may be out of date, or the page
          may have moved.
        </Text>
        <Button component={RouterLink} to="/">
          Back to Users
        </Button>
      </Stack>
    </Container>
  );
});
