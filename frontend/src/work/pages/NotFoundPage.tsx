import { observer } from "mobx-react-lite";
import { Anchor, Container, Stack, Text, Title } from "@mantine/core";

/**
 * The work SPA's terminal `path="*"` page: a not-found message and a plain anchor
 * back to the bookshelf at `/` (a cross-entry link, so a plain `<a>`, not a router
 * link — the bookshelf lives in the user SPA).
 */
export const NotFoundPage = observer(function NotFoundPage() {
  return (
    <Container size="lg" py="md">
      <Stack align="flex-start" gap="sm">
        <Title order={3}>Page not found</Title>
        <Text c="dimmed">
          This workspace address does not exist. The link may be out of date, or the
          page may have moved.
        </Text>
        <Anchor href="/">Back to bookshelf</Anchor>
      </Stack>
    </Container>
  );
});
