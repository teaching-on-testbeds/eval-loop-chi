$(document).ready(function () {
    // Init
    $('.image-section').hide();
    $('.loader').hide();
    $('#result').hide();
    
    // Upload Preview
    function readURL(input) {
        if (input.files && input.files[0]) {
            var reader = new FileReader();
            reader.onload = function (e) {
                $('#imagePreview').css('background-image', 'url(' + e.target.result + ')');
                $('#imagePreview').hide();
                $('#imagePreview').fadeIn(650);
            }
            reader.readAsDataURL(input.files[0]);
        }
    }
    
    $("#imageUpload").change(function () {
        $('.image-section').show();
        $('#btn-predict').show();
        $('#result').text('');
        $('#result').hide();
        readURL(this);
    });
    
    // Use event delegation for dynamically added elements
    $(document).on('click', '.feedback-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        var predictionId = $(this).data('prediction-id');
        var $flagButton = $(this);
        
        console.log('Feedback button clicked, prediction ID:', predictionId);
        
        // Send feedback to server
        $.ajax({
            type: 'POST',
            url: '/feedback',
            data: JSON.stringify({ prediction_id: predictionId }),
            contentType: 'application/json',
            dataType: 'json',
            success: function(response) {
                console.log('Feedback response received:', response);
                // Show alert for now as fallback
                alert('Thank you for your feedback!');
                
            },
            error: function(xhr, status, error) {
                console.error('Feedback error:', status, error);
                console.error('Response:', xhr.responseText);
                alert('Error submitting feedback. Please try again.');
            }
        });
    });
    
    // Predict
    $('#btn-predict').click(function () {
        var form_data = new FormData($('#upload-file')[0]);
        // Show loading animation
        $(this).hide();
        $('.loader').show();
        // Make prediction by calling api /predict
        $.ajax({
            type: 'POST',
            url: '/predict',
            data: form_data,
            contentType: false,
            cache: false,
            processData: false,
            async: true,
            success: function (data) {
                // Get and display the result
                $('.loader').hide();
                $('#result').fadeIn(600);
                $('#result').html(data);
                
                // Initialize tooltips for dynamically added content
                try {
                    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
                        new bootstrap.Tooltip(tooltipTriggerEl);
                    });
                } catch (e) {
                    console.error('Error initializing tooltips:', e);
                }
            },
            error: function(xhr, status, error) {
                console.error('Prediction error:', status, error);
                $('.loader').hide();
                $('#result').fadeIn(600);
                $('#result').text('Error: Could not reach server. Please try again.');
            }
        });
    });
});