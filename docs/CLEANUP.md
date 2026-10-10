# Clean up the lab

Save any reports you need before deleting resources. Never export the model API key.

## Kubernetes only

Confirm kubectl targets your disposable cluster, then delete the two dedicated lab namespaces:

```bash
kubectl config current-context
kubectl delete namespace ai-agent ai-sre-lab
```

This deletes the demo applications, agent Pods, executor Jobs, audit ConfigMaps and model Secret in those namespaces. It does not terminate an EC2 instance.

## Dedicated EC2 lab

In AWS, verify the instance ID and lab tags before terminating the dedicated host.
Confirm its root disk has DeleteOnTermination enabled. After termination, verify:

- The instance is terminated.
- Its lab EBS volume and network interface are gone.
- Its dedicated security group is deleted after interfaces detach.
- No lab-owned Elastic IP, snapshot or other billable resource remains.

Retain pre-existing shared VPCs, subnets and IAM roles. Stopping the instance alone leaves storage charges. Termination permanently removes data on disks configured for deletion.

## Original environment

A tag-checked teardown was started on October 6, 2026 after preserving private audit evidence. Its completion was not captured. A fresh AWS verification on October 10 was blocked by rejected local credentials, so complete deletion is not claimed here.
