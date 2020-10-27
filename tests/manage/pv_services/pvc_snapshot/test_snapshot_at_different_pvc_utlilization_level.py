import logging
import pytest
from copy import deepcopy

from ocs_ci.ocs import constants
from ocs_ci.ocs.resources import pod
from ocs_ci.framework.testlib import skipif_ocs_version, ManageTest, tier1
from ocs_ci.ocs.resources.pod import get_used_space_on_mount_point
from tests.helpers import wait_for_resource_state

log = logging.getLogger(__name__)


@tier1
@skipif_ocs_version('<4.6')
@pytest.mark.polarion_id('OCS-2318')
class TestSnapshotAtDifferentPvcUsageLevel(ManageTest):
    """
    Tests to take snapshot when PVC usage is at different levels
    """
    @pytest.fixture(autouse=True)
    def setup(
        self, project_factory, snapshot_restore_factory, create_pvcs_and_pods
    ):
        """
        Create PVCs and pods

        """
        self.pvc_size = 10
        self.pvcs, self.pods = create_pvcs_and_pods(
            pvc_size=self.pvc_size,
            access_modes_rbd=[constants.ACCESS_MODE_RWO],
            access_modes_cephfs=[constants.ACCESS_MODE_RWO]
        )

    def test_snapshot_at_different_usage_level(
        self, snapshot_factory, snapshot_restore_factory, pod_factory
    ):
        """
        Test to take multiple snapshots of same PVC when the PVC usage is at
        0%, 20%, 40%, 60%, and 80%, then delete the parent PVC and restore the
        snapshots to create new PVCs. Delete snapshots and attach the restored
        PVCs to pods to verify the data.

        """
        snapshots = []
        usage_percent = [0, 20]
        for usage in usage_percent:
            if usage != 0:
                for pod_obj in self.pods:
                    log.info(
                        f"Running IO on pod {pod_obj.name} to utilize {usage}%"
                    )
                    pod_obj.pvc.filename = f'{pod_obj.name}_{usage}'
                    pod_obj.run_io(
                        storage_type='fs',
                        size=f'{int(self.pvc_size/len(usage_percent))}G',
                        runtime=20, fio_filename=pod_obj.pvc.filename
                    )
                log.info(f"IO started on all pods to utilize {usage}%")

                for pod_obj in self.pods:
                    # Wait for fio to finish
                    pod_obj.get_fio_results()
                    log.info(
                        f"IO to utilize {usage}% finished on pod "
                        f"{pod_obj.name}"
                    )
                    # Calculate md5sum
                    md5_sum = pod.cal_md5sum(pod_obj, pod_obj.pvc.filename)
                    if not getattr(pod_obj.pvc, 'md5_sum', None):
                        setattr(pod_obj.pvc, 'md5_sum', {})
                    pod_obj.pvc.md5_sum[pod_obj.pvc.filename] = md5_sum

            # Take snapshot of all PVCs
            log.info(f"Creating snapshot of all PVCs at {usage}%")
            for pvc_obj in self.pvcs:
                log.info(
                    f"Creating snapshot of PVC {pvc_obj.name} at {usage}%"
                )
                snap_obj = snapshot_factory(pvc_obj, wait=False)
                # Set a dict containing filename:md5sum for later verification
                setattr(
                    snap_obj, 'md5_sum',
                    deepcopy(getattr(pvc_obj, 'md5_sum', {}))
                )
                snap_obj.usage_on_mount = get_used_space_on_mount_point(
                    pvc_obj.get_attached_pods()[0]
                )
                snapshots.append(snap_obj)
                log.info(f"Created snapshot of PVC {pvc_obj.name} at {usage}%")
            log.info(f"Created snapshot of all PVCs at {usage}%")
        log.info("Snapshots creation completed.")

        # Verify snapshots are ready
        log.info("Verify snapshots are ready")
        for snapshot in snapshots:
            snapshot.ocp.wait_for_resource(
                condition='true', resource_name=snapshot.name,
                column=constants.STATUS_READYTOUSE, timeout=90
            )

        log.info("Snapshots are Ready. Failing test case now")
        raise Exception("Failing test case to collect must-gather")
