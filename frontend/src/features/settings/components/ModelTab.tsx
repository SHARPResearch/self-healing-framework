import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export function ModelTab() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h3 className="text-base font-semibold">Model configuration</h3>
        <p className="text-sm text-muted-foreground">
          HalfSpaceTrees hyperparameters and ADWIN drift detection, applied to newly initialised
          models.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-border/60 p-4">
        <h4 className="text-sm font-medium">HalfSpaceTrees</h4>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="n-trees">n_trees</Label>
            <Input id="n-trees" type="number" defaultValue="25" />
            <p className="text-xs text-muted-foreground">More trees, more stable scores, slower.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="height">height</Label>
            <Input id="height" type="number" defaultValue="15" />
            <p className="text-xs text-muted-foreground">
              Node count is 2^height, so this grows exponentially.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="window-size">window_size</Label>
            <Input id="window-size" type="number" defaultValue="250" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="seed">seed</Label>
            <Input id="seed" type="number" defaultValue="42" />
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-border/60 p-4">
        <h4 className="text-sm font-medium">ADWIN drift detection</h4>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="adwin-delta">delta</Label>
            <Input id="adwin-delta" type="number" step="0.001" defaultValue="0.002" />
            <p className="text-xs text-muted-foreground">False positive rate, 0.002 is 0.2%.</p>
          </div>
        </div>
        <div className="flex items-center justify-between gap-4 rounded-lg border border-border/60 p-3">
          <div>
            <Label htmlFor="auto-rollback">Auto rollback on drift</Label>
            <p className="text-xs text-muted-foreground">
              Load the last production snapshot when ADWIN fires.
            </p>
          </div>
          <Switch id="auto-rollback" defaultChecked />
        </div>
        <div className="flex items-center justify-between gap-4 rounded-lg border border-border/60 p-3">
          <div>
            <Label htmlFor="auto-promote">Auto promote candidates</Label>
            <p className="text-xs text-muted-foreground">
              Promote a candidate run to production without review.
            </p>
          </div>
          <Switch id="auto-promote" />
        </div>
      </section>

      <Button size="sm">Save model settings</Button>
    </div>
  );
}
