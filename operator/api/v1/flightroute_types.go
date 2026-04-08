package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	runtime "k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

// GroupVersion is group version used to register these objects
var GroupVersion = schema.GroupVersion{
	Group:   "ops.kumarrajapuvvalla-bit.github.io",
	Version: "v1",
}

var (
	// SchemeBuilder is used to add functions to this group's scheme
	SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}

	// AddToScheme adds the types in this group-version to the given scheme
	AddToScheme = SchemeBuilder.AddToScheme
)

func init() {
	SchemeBuilder.Register(&FlightRoute{}, &FlightRouteList{})
}

// FlightRouteSpec defines the desired state of FlightRoute
type FlightRouteSpec struct {
	// RouteName is the IATA flight route code (e.g. "LHR-JFK")
	// +kubebuilder:validation:Pattern=`^[A-Z]{3}-[A-Z]{3}$`
	RouteName string `json:"routeName"`

	// MinReplicas is the minimum number of pods the backing Deployment must maintain
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=20
	MinReplicas int32 `json:"minReplicas"`

	// SloTarget is the availability SLO percentage (e.g. 99.9)
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=100
	SloTarget float64 `json:"sloTarget"`

	// BackingDeployment is the name of the Deployment this FlightRoute controls
	BackingDeployment string `json:"backingDeployment"`

	// HealingEnabled controls whether the operator will auto-scale the deployment.
	// +kubebuilder:default=true
	HealingEnabled bool `json:"healingEnabled,omitempty"`
}

// FlightRouteStatus defines the observed state of FlightRoute
type FlightRouteStatus struct {
	// CurrentReplicas is the number of replicas observed on the backing Deployment
	CurrentReplicas int32 `json:"currentReplicas,omitempty"`

	// LastHealedAt is the timestamp of the last auto-healing action
	// +optional
	LastHealedAt *metav1.Time `json:"lastHealedAt,omitempty"`

	// HealCount is the total number of times this route has been auto-healed
	HealCount int32 `json:"healCount,omitempty"`

	// Conditions stores standard Kubernetes conditions for the FlightRoute
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`

	// SloCompliant indicates whether the route is currently meeting its SLO target
	SloCompliant bool `json:"sloCompliant,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:printcolumn:name="Route",type=string,JSONPath=`.spec.routeName`
// +kubebuilder:printcolumn:name="MinReplicas",type=integer,JSONPath=`.spec.minReplicas`
// +kubebuilder:printcolumn:name="HealCount",type=integer,JSONPath=`.status.healCount`
// +kubebuilder:printcolumn:name="SLO",type=number,JSONPath=`.spec.sloTarget`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// FlightRoute is the Schema for the flightroutes API
type FlightRoute struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   FlightRouteSpec   `json:"spec,omitempty"`
	Status FlightRouteStatus `json:"status,omitempty"`
}

// DeepCopyObject implements runtime.Object.
func (in *FlightRoute) DeepCopyObject() runtime.Object {
	out := new(FlightRoute)
	*out = *in
	return out
}

// +kubebuilder:object:root=true

// FlightRouteList contains a list of FlightRoute
type FlightRouteList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []FlightRoute `json:"items"`
}

// DeepCopyObject implements runtime.Object.
func (in *FlightRouteList) DeepCopyObject() runtime.Object {
	out := new(FlightRouteList)
	*out = *in
	return out
}
