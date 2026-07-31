import { observer } from "mobx-react-lite";
import { Anchor, Container, Stack, Text, Title } from "@mantine/core";

/**
 * The reader SPA's terminal `path="*"` page (feature 022).
 *
 * A static not-found message plus a plain `<a href="/">` back to the bookshelf —
 * a cross-entry link, so a plain anchor and not a router link (the
 * `src/work/pages/NotFoundPage.tsx` shape). It links to no authoring surface, and
 * it discloses nothing about whether a book exists at the attempted address: the
 * copy is the same whatever the address was.
 */
export const NotFoundPage = observer(function NotFoundPage() {
  return (
    <Container size="md" py="md">
      <Stack align="flex-start" gap="sm">
        <Title order={3}>Page not found</Title>
        <Text c="dimmed">
          This reading address does not exist. The link may be out of date, or the
          page may have moved.
        </Text>
        <Anchor href="/">Back to bookshelf</Anchor>
      </Stack>
    </Container>
  );
});
