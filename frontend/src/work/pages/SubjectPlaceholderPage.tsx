import { observer } from "mobx-react-lite";
import { Container, Stack, Text, Title } from "@mantine/core";

/**
 * A read-only content-pane empty state used by every list route and every item
 * route step 004 adds. The lists have no backing endpoint yet (feature 008 landed
 * tables and `db/` modules only), so each route names the roadmap folder that
 * owns the real view. Structural placeholder: a heading and an owner label, no
 * state, no data, no behaviour.
 */
export interface SubjectPlaceholderPageProps {
  /** Author-facing heading for the subject, e.g. `"Chapters"`. */
  heading: string;
  /** The roadmap folder that owns the real view, e.g. `"014.chapter-skeleton"`. */
  owner: string;
}

export const SubjectPlaceholderPage = observer(function SubjectPlaceholderPage({
  heading,
  owner,
}: SubjectPlaceholderPageProps) {
  return (
    <Container size="lg" py="md">
      <Stack align="flex-start" gap="sm">
        <Title order={3}>{heading}</Title>
        <Text c="dimmed">This view is delivered by {owner}.</Text>
      </Stack>
    </Container>
  );
});
