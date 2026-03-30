/**
 * manage-schedule Edge Function
 *
 * Replaces create-eventbridge-schedule and delete-schedule Lambdas.
 * Creates/deletes pg_cron jobs and manages scout records via the FastAPI backend.
 *
 * Actions:
 *   create -> Create scout record + pg_cron schedule
 *   delete -> Delete scout record + pg_cron schedule
 *   update -> Update scout record + pg_cron schedule
 */
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const INTERNAL_SERVICE_KEY = Deno.env.get("INTERNAL_SERVICE_KEY") ?? "";

/**
 * Build the pg_cron command that fires pg_net.http_post to the execute-scout
 * Edge Function. Uses the schedule_cron_job RPC wrapper (from Fix 7) which
 * accepts the command as a parameterized function argument, avoiding SQL
 * injection from user-controlled values like scout_id or scout_name.
 */
function buildCronCommand(scoutId: string, userId: string, scoutType: string, scoutName: string): string {
  // The body is a JSON literal embedded in the SQL command string.
  // This is safe because the RPC wrapper passes it as a parameter to cron.schedule().
  const body = JSON.stringify({
    scout_id: scoutId,
    user_id: userId,
    scout_type: scoutType,
    scraper_name: scoutName,
  });
  const headers = JSON.stringify({
    "Content-Type": "application/json",
    "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`,
  });
  return `SELECT net.http_post(url := '${SUPABASE_URL}/functions/v1/execute-scout', headers := '${headers}'::jsonb, body := '${body}'::jsonb, timeout_milliseconds := 60000)`;
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // Verify authorization (exact match, not substring)
    const authHeader = req.headers.get("Authorization") ?? "";
    const expectedToken = `Bearer ${SUPABASE_SERVICE_KEY}`;

    if (!SUPABASE_SERVICE_KEY) {
      return new Response(
        JSON.stringify({ error: "Server misconfigured: missing service key" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    if (authHeader !== expectedToken) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const action: string = body.action ?? "";

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
      auth: { persistSession: false },
    });

    switch (action) {
      case "create": {
        const {
          user_id,
          scout_name,
          scout_type,
          schedule_name,
          cron_expression,
          scout_config,
        } = body;

        // 1. Create scout record in the database
        const { data: scout, error: scoutError } = await supabase
          .from("scouts")
          .insert({
            user_id,
            name: scout_name,
            type: scout_type,
            schedule_cron: cron_expression,
            is_active: true,
            ...scout_config,
          })
          .select()
          .single();

        if (scoutError) {
          console.error("Failed to create scout:", scoutError);
          return new Response(
            JSON.stringify({ error: "Failed to create scout", detail: scoutError.message }),
            { status: 500, headers: { "Content-Type": "application/json" } },
          );
        }

        // 2. Create pg_cron job via RPC wrapper (avoids direct SQL injection)
        const cronCommand = buildCronCommand(scout.id, user_id, scout_type, scout_name);

        const { error: cronError } = await supabase.rpc("schedule_cron_job", {
          job_name: schedule_name,
          cron_expr: cron_expression,
          command: cronCommand,
        });

        if (cronError) {
          console.error("Failed to create cron job:", cronError);
          // Clean up the scout record
          await supabase.from("scouts").delete().eq("id", scout.id);
          return new Response(
            JSON.stringify({ error: "Failed to create schedule", detail: cronError.message }),
            { status: 500, headers: { "Content-Type": "application/json" } },
          );
        }

        console.log(`Created schedule: ${schedule_name} for scout ${scout.id}`);
        return new Response(
          JSON.stringify({ scout_id: scout.id, schedule_name }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      case "delete": {
        const { schedule_name: deleteName, scout_id } = body;

        // 1. Delete pg_cron job
        const { error: unscheduleError } = await supabase.rpc("unschedule_cron_job", {
          job_name: deleteName,
        });

        if (unscheduleError) {
          console.error("Failed to delete cron job:", unscheduleError);
          // Continue to delete scout record even if cron deletion fails
        }

        // 2. Delete scout record (CASCADE handles related records)
        if (scout_id) {
          const { error: deleteError } = await supabase
            .from("scouts")
            .delete()
            .eq("id", scout_id);

          if (deleteError) {
            console.error("Failed to delete scout:", deleteError);
          }
        }

        console.log(`Deleted schedule: ${deleteName}`);
        return new Response(
          JSON.stringify({ deleted: deleteName }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      case "update": {
        const {
          schedule_name: updateName,
          scout_id: updateScoutId,
          cron_expression: newCron,
          scout_config: updateConfig,
        } = body;

        // Update scout record
        if (updateScoutId && updateConfig) {
          const { error: updateError } = await supabase
            .from("scouts")
            .update(updateConfig)
            .eq("id", updateScoutId);

          if (updateError) {
            console.error("Failed to update scout:", updateError);
          }
        }

        // If cron changed, delete and recreate the cron job via RPC wrapper
        if (newCron && updateName) {
          await supabase.rpc("unschedule_cron_job", { job_name: updateName });

          const cronCommand = buildCronCommand(
            updateScoutId,
            body.user_id,
            body.scout_type,
            body.scout_name ?? "",
          );

          const { error: rescheduleError } = await supabase.rpc("schedule_cron_job", {
            job_name: updateName,
            cron_expr: newCron,
            command: cronCommand,
          });

          if (rescheduleError) {
            console.error("Failed to reschedule:", rescheduleError);
          }
        }

        console.log(`Updated schedule: ${updateName}`);
        return new Response(
          JSON.stringify({ updated: updateName }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      default:
        return new Response(
          JSON.stringify({ error: `Unknown action: ${action}` }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
    }
  } catch (error) {
    console.error("Error in manage-schedule:", error);
    return new Response(
      JSON.stringify({
        error: "Internal server error",
        detail: error instanceof Error ? error.message : String(error),
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});
