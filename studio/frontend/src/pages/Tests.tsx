import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTests, useDeleteTest, useTriggerRun } from '../hooks/useApi';
import { Button, PageHeader, ErrorState, ConfirmDialog, toast, EmptyState } from '../components/ui';
import { Play, Trash2, Eye, Plus, ShieldAlert, CheckCircle } from 'lucide-react';

export default function Tests() {
  const navigate = useNavigate();
  const { data: tests, isLoading, error, refetch } = useTests();
  const deleteMutation = useDeleteTest();
  const triggerRunMutation = useTriggerRun();

  const [testToDelete, setTestToDelete] = useState<number | null>(null);

  const confirmDelete = async () => {
    if (testToDelete !== null) {
      try {
        await deleteMutation.mutateAsync(testToDelete);
        toast.success('Test deleted successfully.');
      } catch (err: any) {
        toast.error(err.message || 'Failed to delete test.');
      } finally {
        setTestToDelete(null);
      }
    }
  };

  const handleRun = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const res = await triggerRunMutation.mutateAsync(id);
      toast.success('Execution run started.');
      navigate(`/runs/${res.run_id}`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to trigger run.');
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 w-full max-w-6xl mx-auto">
        <div className="flex justify-between items-center">
          <div className="h-10 w-48 bg-slate-800/50 rounded-lg animate-pulse"></div>
          <div className="h-10 w-32 bg-slate-800/50 rounded-lg animate-pulse"></div>
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-20 bg-slate-800/40 rounded-xl animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 w-full max-w-2xl mx-auto">
        <ErrorState
          message="Failed to load test suite."
          details={error instanceof Error ? error.stack : String(error)}
          onRetry={refetch}
        />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 w-full max-w-7xl mx-auto">
      <PageHeader
        title="Test Suite"
        description="Manage, record, and trigger local automated test definitions"
        actions={
          <Button onClick={() => navigate('/tests/new')} className="gap-2">
            <Plus className="w-4 h-4" />
            <span>New Test</span>
          </Button>
        }
      />

      {!tests || tests.length === 0 ? (
        <div className="max-w-2xl mx-auto">
          <EmptyState
            icon={<ShieldAlert className="h-8 w-8" />}
            title="No Tests Recorded"
            description="ScrapeWizard is a record-first automation framework. Record browser actions to generate robust, self-healing test definitions."
            action={{
              label: "Record Your First Test",
              onClick: () => navigate('/tests/new'),
            }}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {tests.map(test => (
            <div
              key={test.id}
              onClick={() => navigate(`/tests/${test.id}`)}
              className="px-6 py-5 bg-surface border border-edge/60 hover:border-slate-700 rounded-xl flex items-center justify-between cursor-pointer transition-all hover:bg-slate-850/20"
            >
              <div className="space-y-1.5 max-w-xl">
                <h3 className="font-bold text-white text-base display-font hover:text-primary transition-colors">{test.name}</h3>
                <p className="text-xs text-text-muted truncate font-mono">{test.url}</p>
                <div className="flex items-center gap-3 pt-1 text-xs">
                  <span className="px-2 py-0.5 bg-slate-850 text-slate-400 border border-edge/40 rounded-md font-medium font-mono text-[10px]">
                    {test.step_count} Steps
                  </span>
                  
                  {test.last_run ? (
                    <div className="flex items-center gap-1.5 text-text-muted text-[11px]">
                      <span>•</span>
                      <span>Last run:</span>
                      <span className={`flex items-center gap-1 font-semibold capitalize ${
                        test.last_run.status === 'passed' ? 'text-pass' : 'text-fail'
                      }`}>
                        {test.last_run.status === 'passed' ? <CheckCircle className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
                        {test.last_run.status}
                      </span>
                    </div>
                  ) : (
                    <span className="text-slate-600 text-[11px]">No runs executed</span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate(`/tests/${test.id}`)}
                  title="View details"
                  className="px-2.5"
                >
                  <Eye className="w-4 h-4" />
                </Button>
                
                <Button
                  size="sm"
                  onClick={(e) => handleRun(e, test.id)}
                  disabled={!test.step_count}
                  loading={triggerRunMutation.isPending && triggerRunMutation.variables === test.id}
                  title="Execute Run"
                  className="px-2.5"
                >
                  <Play className="w-4 h-4 fill-white" />
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setTestToDelete(test.id)}
                  title="Delete test"
                  className="px-2.5 text-slate-400 hover:text-fail hover:bg-fail/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={testToDelete !== null}
        title="Delete Test?"
        description="Are you sure you want to delete this test? All recorded step definitions and run execution records will be lost permanently."
        confirmLabel="Delete"
        isDanger={true}
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setTestToDelete(null)}
      />
    </div>
  );
}
