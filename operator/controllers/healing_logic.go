package controllers

import (
	"context"
	"fmt"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/log"

	opsv1 "github.com/kumarrajapuvvalla-bit/ops-platform/operator/api/v1"
)

// healDeployment scales a Deployment back up to minReplicas, records a
// Kubernetes Event, and updates the FlightRoute audit fields.
func (r *FlightRouteReconciler) healDeployment(
	ctx context.Context,
	flightRoute *opsv1.FlightRoute,
	deployment *appsv1.Deployment,
	targetReplicas int32,
) error {
	logger := log.FromContext(ctx)

	previous := *deployment.Spec.Replicas
	deployment.Spec.Replicas = &targetReplicas

	if err := r.Update(ctx, deployment); err != nil {
		return fmt.Errorf("scale deployment %s to %d: %w",
			deployment.Name, targetReplicas, err)
	}

	logger.Info("Self-healing applied",
		"deployment", deployment.Name,
		"previous", previous,
		"restored", targetReplicas,
		"route", flightRoute.Spec.RouteCode,
	)

	// Emit a Kubernetes Event for audit visibility in kubectl describe
	r.Recorder.Eventf(
		flightRoute,
		corev1.EventTypeWarning,
		"SelfHealingTriggered",
		"Route %s: scaled deployment %s from %d to %d replicas (drift detected)",
		flightRoute.Spec.RouteCode,
		deployment.Name,
		previous,
		targetReplicas,
	)

	// Update audit fields on the FlightRoute
	now := metav1.NewTime(time.Now())
	flightRoute.Status.LastHealedAt = &now
	flightRoute.Status.HealingCount++
	flightRoute.Status.CurrentReplicas = targetReplicas

	return nil
}
